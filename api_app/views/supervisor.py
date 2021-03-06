# -*- coding: utf-8 -*-
# Copyright (C) 2018 Freetech Solutions

# This file is part of OMniLeads

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses/.
#

from __future__ import unicode_literals

import logging as _logging

import datetime
import json
import threading

import redis

from collections import OrderedDict
from django.views.generic import View
from django.utils.translation import ugettext as _
from django.utils.timezone import now
from django.http import JsonResponse
from django.db.models import Count
from django.conf import settings

from rest_framework import viewsets
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from simple_history.utils import update_change_reason

from api_app.views.permissions import TienePermisoOML
from api_app.serializers import (CampanaSerializer, )
from ominicontacto_app.models import (
    Campana, CalificacionCliente, AgenteProfile, AgendaContacto, AgenteEnContacto)
from ominicontacto_app.services.asterisk.supervisor_activity import SupervisorActivityAmiManager
from reportes_app.reportes.reporte_llamadas_supervision import (
    ReporteDeLLamadasEntrantesDeSupervision, )
from reportes_app.reportes.reporte_llamadas import ReporteTipoDeLlamadasDeCampana
from reportes_app.reportes.reporte_llamados_contactados_csv import (
    ExportacionCampanaCSV, ReporteCalificadosCSV, ReporteContactadosCSV, ReporteNoAtendidosCSV)
from reportes_app.reportes.reporte_llamadas_salientes import ReporteLlamadasSalienteFamily
from ominicontacto_app.utiles import datetime_hora_minima_dia, convert_fecha_datetime

logger = _logging.getLogger(__name__)


class SupervisorCampanasActivasViewSet(viewsets.ModelViewSet):
    """Servicio que devuelve las campa??as activas relacionadas a un supervisor
    si este no es admin y todas las campa??as activas en el caso de s?? lo sea
    """
    serializer_class = CampanaSerializer
    permission_classes = (TienePermisoOML, )
    queryset = Campana.objects.obtener_activas()
    http_method_names = ['get']

    def get_queryset(self):
        superv_profile = self.request.user.get_supervisor_profile()
        if superv_profile.is_administrador:
            return super(SupervisorCampanasActivasViewSet, self).get_queryset()
        return superv_profile.obtener_campanas_asignadas_activas()


class AgentesStatusAPIView(APIView):
    """Devuelve informaci??n de los agentes en el sistema"""
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['get']

    def _obtener_datos_agentes(self, supervisor_pk):
        redis_connection = redis.Redis(
            host=settings.REDIS_HOSTNAME,
            port=settings.CONSTANCE_REDIS_CONNECTION['port'],
            decode_responses=True)
        response = redis_connection.hgetall('OML:SUPERVISOR:{0}'.format(supervisor_pk))
        result = {}
        for agent_id, dato in response.items():
            result[agent_id] = json.loads(dato)
        return result

    def _obtener_ids_agentes_propios(self, request):
        supervisor_pk = request.user.get_supervisor_profile().pk
        agentes_dict = self._obtener_datos_agentes(supervisor_pk)
        return agentes_dict

    def get(self, request):
        online = []
        agentes_parseados = SupervisorActivityAmiManager()
        agentes_dict = self._obtener_ids_agentes_propios(request)
        for data_agente in agentes_parseados.obtener_agentes_activos():
            id_agente = int(data_agente.get('id', -1))
            status_agente = data_agente.get('status', '')
            if status_agente != 'OFFLINE' and str(id_agente) in agentes_dict:
                agente_dict = agentes_dict.get(str(id_agente), '')
                grupo_activo = agente_dict.get('grupo', '')
                campanas_activas = agente_dict.get('campana', [])
                data_agente['grupo'] = grupo_activo
                data_agente['campana'] = campanas_activas
                online.append(data_agente)
        return Response(data=online)


class StatusCampanasEntrantesView(APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['get']

    def get(self, request):
        reporte = ReporteDeLLamadasEntrantesDeSupervision(request.user)
        return Response(data={'errors': None,
                              'data': reporte.estadisticas})


class StatusCampanasSalientesView(APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['get']

    def _obtener_datos_campanas(self, user):
        redis_saliente = ReporteLlamadasSalienteFamily()
        if not user.is_supervisor:
            campanas = Campana.objects.all()
        else:
            campanas = user.get_supervisor_profile().obtener_campanas_asignadas_activas()
        query_campanas = campanas.filter(
            type__in=[Campana.TYPE_DIALER,
                      Campana.TYPE_PREVIEW,
                      Campana.TYPE_MANUAL])
        data_saliente = []
        for campana in query_campanas:
            estadisticas = redis_saliente.get_value(campana, 'ESTADISTICAS')
            if estadisticas:
                data_saliente.append(json.loads(estadisticas))
        return data_saliente

    def get(self, request):
        supervisor_pk = request.user
        datos_campana = self._obtener_datos_campanas(supervisor_pk)
        return Response(data=datos_campana)


class InteraccionDeSupervisorSobreAgenteView(APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['post']

    def dispatch(self, request, *args, **kwargs):
        self.supervisor = self.request.user.get_supervisor_profile()
        self.agente_id = kwargs.get('pk')
        # TODO: Verificar que el supervisor sea responsable del agente.
        return super(InteraccionDeSupervisorSobreAgenteView, self).dispatch(
            request, *args, **kwargs)

    def post(self, request, pk):
        accion = request.POST.get('accion')
        servicio_acciones = SupervisorActivityAmiManager()
        error = servicio_acciones.ejecutar_accion_sobre_agente(
            self.supervisor, self.agente_id, accion)
        if error:
            return Response(data={
                'status': 'ERROR',
                'message': error
            })
        else:
            return Response(data={
                'status': 'OK',
            })


class ReasignarAgendaContactoView(APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['post', ]

    def post(self, request):
        agenda_id = request.data.get('agenda_id')
        agente_id = request.data.get('agent_id')

        try:
            agenda = AgendaContacto.objects.get(id=agenda_id,
                                                tipo_agenda=AgendaContacto.TYPE_PERSONAL)
        except AgendaContacto.DoesNotExist:
            return Response(data={
                'status': 'ERROR',
                'message': _('ID Agenda incorrecto')
            })
        try:
            agente = agenda.campana.queue_campana.members.get(id=agente_id)
        except AgenteProfile.DoesNotExist:
            return Response(data={
                'status': 'ERROR',
                'message': _('ID Agente incorrecto')
            })

        supervisor_profile = self.request.user.get_supervisor_profile()
        campanas_asignadas_actuales = supervisor_profile.campanas_asignadas_actuales()
        if not campanas_asignadas_actuales.filter(id=agenda.campana.id).exists():
            return Response(data={
                'status': 'ERROR',
                'message': _('No tiene permiso para editar esta Agenda')
            })

        agenda.agente = agente
        agenda.save()
        calificacion = CalificacionCliente.objects.get(contacto=agenda.contacto,
                                                       opcion_calificacion__campana=agenda.campana)
        calificacion.agente = agente
        calificacion.save()
        update_change_reason(calificacion, 'reasignacion')

        return Response(data={
            'status': 'OK',
            'agenda_id': agenda_id,
            'agent_name': agente.user.get_full_name()
        })


class DataAgendaContactoView(APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['get', ]

    def get(self, request, agenda_id):

        try:
            agenda = AgendaContacto.objects.get(id=agenda_id,
                                                tipo_agenda=AgendaContacto.TYPE_PERSONAL)
        except AgendaContacto.DoesNotExist:
            return Response(data={
                'status': 'ERROR',
                'message': _('ID Agenda incorrecto')
            })
        supervisor_profile = self.request.user.get_supervisor_profile()
        campanas_asignadas_actuales = supervisor_profile.campanas_asignadas_actuales()
        if not campanas_asignadas_actuales.filter(id=agenda.campana.id).exists():
            return Response(data={
                'status': 'ERROR',
                'message': _('No tiene permiso para editar esta Agenda')
            })

        contact_data = agenda.contacto.obtener_datos()
        return Response(data={
            'status': 'OK',
            'agenda_id': agenda_id,
            'observations': agenda.observaciones,
            'contact_data': contact_data
        })


# ########################################################
# TODO: Funcionalidad vieja que podria volver a utilizarse
class LlamadasDeCampanaView(View):
    """
    Devuelve un JSON con cantidades de tipos de llamadas de la campa??a para el dia de la fecha
    """
    TIPOS = OrderedDict([
        ("recibidas", _(u'Recibidas')),
        ('efectuadas', _(u'Efectuadas')),
        ("atendidas", _(u'Atendidas')),
        ('conectadas', _(u'Conectadas')),
        ('no_conectadas', _(u'No Conectadas')),
        ("abandonadas", _(u'Abandonadas')),
        ("expiradas", _(u'Expiradas')),
        ("t_espera_conexion", _(u'Tiempo de Espera de Conexi??n(prom.)')),
        ('t_espera_atencion', _(u'Tiempo de Espera de Atenci??n(prom.)')),
        ("t_abandono", _(u'Tiempo de Abandono(prom.)')),
    ])
    TIPOS_MANUALES = OrderedDict([
        ("efectuadas_manuales", _(u'Efectuadas Manuales')),
        ("conectadas_manuales", _(u'Conectadas Manuales')),
        ("no_conectadas_manuales", _(u'No Conectadas Manuales')),
        ("t_espera_conexion_manuales", _(u'Tiempo de Espera de Conexi??n Manuales(prom.)')),
    ])

    def get(self, request, pk_campana):
        hoy_ahora = now()
        hoy_inicio = datetime_hora_minima_dia(hoy_ahora)
        try:
            reporte = ReporteTipoDeLlamadasDeCampana(hoy_inicio, hoy_ahora, pk_campana)
            reporte.estadisticas.pop('nombre')
            data = {'status': 'OK', 'llamadas': []}
            for campo, nombre in self.TIPOS.iteritems():
                if campo in reporte.estadisticas:
                    data['llamadas'].append((nombre, reporte.estadisticas[campo]))
            for campo, nombre in self.TIPOS_MANUALES.iteritems():
                if campo in reporte.estadisticas:
                    if 'manuales' not in data:
                        data['manuales'] = []
                    data['manuales'].append((nombre, reporte.estadisticas[campo]))

        except Campana.DoesNotExist:
            data = {'status': 'Error', 'error_message': _(u'No existe la campa??a')}

        return JsonResponse(data=data)


class CalificacionesDeCampanaView(View):
    """
    Devuelve un JSON con cantidades de cada tipo de calificaci??n de una campa??a del dia de la fecha
    """
    def get(self, request, pk_campana):

        try:
            campana = Campana.objects.get(id=pk_campana)
        except Campana.DoesNotExist:
            return JsonResponse(data={'status': 'Error',
                                      'error_message': _(u'No existe la campa??a')})

        data = {'status': 'OK'}
        for opcion in campana.opciones_calificacion.all():
            data[opcion.nombre] = 0
        calificaciones = CalificacionCliente.objects.filter(
            fecha__gt=datetime_hora_minima_dia(now()),
            opcion_calificacion__campana_id=pk_campana)
        cantidades = calificaciones.values('opcion_calificacion__nombre').annotate(
            cantidad=Count('opcion_calificacion__nombre')).order_by()

        for opcion in cantidades:
            data[opcion['opcion_calificacion__nombre']] = opcion['cantidad']

        return JsonResponse(data=data)


class ExportarCSVMixin:

    def loguear_inicio_exportacion(
            self, tipo, campana_id, supervisor_nombre, fecha_hasta, fecha_desde):
        cadena_inicio_exportacion_info = (
            "Generating CSV report of {0} campaign {1}  from user {2}. ".format(
                tipo, campana_id, supervisor_nombre)) + \
            "Date filter: from {0} to {1}".format(fecha_hasta, fecha_desde)
        logger.info(cadena_inicio_exportacion_info)


class ExportarCSVContactados(ExportarCSVMixin, APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['post', ]

    def generar_csv_contactados(self, key_task, campana, desde, hasta):

        reporte_contactados_csv = ReporteContactadosCSV(
            campana, key_task, desde, hasta)
        datos_contactados = reporte_contactados_csv.datos
        service_csv = ExportacionCampanaCSV()
        service_csv.exportar_reportes_csv(campana, datos_contactados=datos_contactados)

    def post(self, request):
        campana_id = request.data.get('campana_id')
        task_id = request.data.get('task_id')
        desde = request.data.get('desde')
        hasta = request.data.get('hasta')
        fecha_desde = convert_fecha_datetime(desde)
        fecha_hasta = convert_fecha_datetime(hasta)
        fecha_desde = datetime.datetime.combine(fecha_desde, datetime.time.min)
        fecha_hasta = datetime.datetime.combine(fecha_hasta, datetime.time.max)
        campana = Campana.objects.get(pk=campana_id)

        # generar id para la operacion de acuerdo a (timestamp, campana, supervisor)
        # obtener de request

        key_task = 'OML:STATUS_CSV_REPORT:CONTACTED:{0}:{1}'.format(campana_id, task_id)
        # chequear si el supervisor esta asignado a la campa??a
        # chequear si la campa??a existe

        thread_exportacion = threading.Thread(
            target=self.generar_csv_contactados, args=[key_task, campana, fecha_desde, fecha_hasta])
        thread_exportacion.setDaemon(True)
        thread_exportacion.start()

        self.loguear_inicio_exportacion(
            'contactados', campana_id, request.user.username, fecha_hasta.strftime("%m/%d/%Y"),
            fecha_desde.strftime("%m/%d/%Y"))

        return Response(data={
            'status': 'OK',
            'msg': _('Exportaci??n de contactados a .csv en proceso'),
            'id': task_id,
        })


class ExportarCSVCalificados(ExportarCSVMixin, APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['post', ]

    def generar_csv_calificados(self, key_task, campana, desde, hasta):

        reporte_calificados_csv = ReporteCalificadosCSV(
            campana, key_task, desde, hasta)
        datos_calificados = reporte_calificados_csv.datos
        service_csv = ExportacionCampanaCSV()
        service_csv.exportar_reportes_csv(campana, datos_calificados=datos_calificados)

    def post(self, request):
        campana_id = request.data.get('campana_id')
        task_id = request.data.get('task_id')
        desde = request.data.get('desde')
        hasta = request.data.get('hasta')
        fecha_desde = convert_fecha_datetime(desde)
        fecha_hasta = convert_fecha_datetime(hasta)
        fecha_desde = datetime.datetime.combine(fecha_desde, datetime.time.min)
        fecha_hasta = datetime.datetime.combine(fecha_hasta, datetime.time.max)
        campana = Campana.objects.get(pk=campana_id)
        # generar id para la operacion de acuerdo a (timestamp, campana, supervisor)
        # obtener de request

        key_task = 'OML:STATUS_CSV_REPORT:DISPOSITIONED:{0}:{1}'.format(campana_id, task_id)

        # chequear si el supervisor esta asignado a la campa??a
        # chequear si la campa??a existe

        thread_exportacion = threading.Thread(
            target=self.generar_csv_calificados, args=[key_task, campana, fecha_desde, fecha_hasta])
        thread_exportacion.setDaemon(True)
        thread_exportacion.start()

        self.loguear_inicio_exportacion(
            'calificados', campana_id, request.user.username, fecha_hasta.strftime("%m/%d/%Y"),
            fecha_desde.strftime("%m/%d/%Y"))

        return Response(data={
            'status': 'OK',
            'msg': _('Exportaci??n de calificados a .csv en proceso'),
            'id': task_id,
        })


class ExportarCSVNoAtendidos(ExportarCSVMixin, APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['post', ]

    def generar_csv_no_atendidos(self, key_task, campana, desde, hasta):

        reporte_no_atendidos_csv = ReporteNoAtendidosCSV(
            campana, key_task, desde, hasta)
        datos_no_atendidos = reporte_no_atendidos_csv.datos
        service_csv = ExportacionCampanaCSV()
        service_csv.exportar_reportes_csv(campana, datos_no_atendidos=datos_no_atendidos)

    def post(self, request):
        campana_id = request.data.get('campana_id')
        task_id = request.data.get('task_id')
        desde = request.data.get('desde')
        hasta = request.data.get('hasta')
        fecha_desde = convert_fecha_datetime(desde)
        fecha_hasta = convert_fecha_datetime(hasta)
        fecha_desde = datetime.datetime.combine(fecha_desde, datetime.time.min)
        fecha_hasta = datetime.datetime.combine(fecha_hasta, datetime.time.max)
        campana = Campana.objects.get(pk=campana_id)
        # generar id para la operacion de acuerdo a (timestamp, campana, supervisor)
        # obtener de request

        key_task = 'OML:STATUS_CSV_REPORT:NOT_ATTENDED:{0}:{1}'.format(campana_id, task_id)

        # chequear si el supervisor esta asignado a la campa??a
        # chequear si la campa??a existe

        thread_exportacion = threading.Thread(
            target=self.generar_csv_no_atendidos,
            args=[key_task, campana, fecha_desde, fecha_hasta])
        thread_exportacion.setDaemon(True)
        thread_exportacion.start()
        self.loguear_inicio_exportacion(
            'no atendidos', campana_id, request.user.username, fecha_hasta.strftime("%m/%d/%Y"),
            fecha_desde.strftime("%m/%d/%Y"))

        return Response(data={
            'status': 'OK',
            'msg': _('Exportaci??n de no atendidos a .csv en proceso'),
            'id': task_id,
        })


class ContactosAsignadosCampanaPreviewView(APIView):
    permission_classes = (TienePermisoOML, )
    renderer_classes = (JSONRenderer, )
    http_method_names = ['get', ]

    def _obtener_estado(self, estado, agente_id):
        if estado == AgenteEnContacto.ESTADO_FINALIZADO:
            return _('Finalizado')
        if estado == AgenteEnContacto.ESTADO_INICIAL and agente_id == -1:
            return _('Liberado')
        else:
            return _('Reservado')

    def _obtener_datos_agente_contacto(self, agentes_contactos, nombres_agentes):
        datos_agente = {}
        for agente_contacto in agentes_contactos:
            datos = {}
            datos['estado'] = self._obtener_estado(agente_contacto.estado,
                                                   agente_contacto.agente_id)
            if not agente_contacto.agente_id == -1:
                datos['agente'] = nombres_agentes[agente_contacto.agente_id]
            else:
                datos['agente'] = ''
            datos_agente[agente_contacto.contacto_id] = datos
        return datos_agente

    def get(self, request, pk_campana):
        campana = Campana.objects.get(id=pk_campana)
        contactos = campana.bd_contacto.contactos.all()
        contactos_ids = [contacto.id for contacto in contactos]
        agentes_contactos = [agente_contacto for agente_contacto in AgenteEnContacto.objects.filter(
            contacto_id__in=contactos_ids)]
        agente_ids = [agente_contacto.agente_id for agente_contacto in agentes_contactos]
        nombres_agentes = {agente.id: agente.user.get_full_name()
                           for agente in AgenteProfile.objects.select_related(
                           'user').filter(pk__in=agente_ids)}
        datos_agente = self._obtener_datos_agente_contacto(agentes_contactos, nombres_agentes)

        data_contacto = []
        for contacto in contactos:
            datos = {}
            datos['id'] = contacto.id
            datos['telefono'] = contacto.telefono
            datos['id_externo'] = contacto.id_externo
            dato_agente = datos_agente[contacto.id]
            if dato_agente:
                datos['estado'] = dato_agente['estado']
                datos['agente'] = dato_agente['agente']
            data_contacto.append(datos)

        return Response(data=data_contacto)
