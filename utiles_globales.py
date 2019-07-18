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

import re

from django.conf import settings
from django.forms import ValidationError
from django.utils.translation import ugettext as _

from ominicontacto_app.errors import OmlArchivoImportacionInvalidoError
from ominicontacto_app.models import CalificacionCliente

from api_app.utiles import EstadoAgentesService

extension_audio_permitidas_regex = re.compile(r'.*\.(wav|mp3)$')


def validar_extension_archivo_audio(valor):
    if valor is not None and not extension_audio_permitidas_regex.match(valor.name):
        raise ValidationError(
            _('Archivos permitidos: .wav, .mp3'), code='invalid')


def obtener_cantidad_no_calificados(total_llamadas_qs, fecha_desde, fecha_hasta, campana):
    total_llamadas_campanas = total_llamadas_qs.count()
    total_calificados = CalificacionCliente.history.filter(
        history_date__range=(fecha_desde, fecha_hasta),
        opcion_calificacion__campana=campana, history_change_reason='calificacion').count()
    total_atendidas_sin_calificacion = total_llamadas_campanas - total_calificados
    if total_atendidas_sin_calificacion < 0:
        # significa que el agente calificó llamadas que no conectaron con el usuario
        total_atendidas_sin_calificacion = 0
    return total_atendidas_sin_calificacion


def validar_estructura_csv(data_csv_memory, err_message, logger):
    """Analiza si un archivo con extensión .csv tiene una estructura válida"""
    try:
        # chequea que el csv tenga un formato estándar de black list, así podemos descartar
        # archivos csv corruptos
        all([row[0] < row[1] for row in data_csv_memory])
    except Exception as e:
        logger.warn("Error: {0}".format(e.message))
        raise(OmlArchivoImportacionInvalidoError(err_message))


def obtener_sip_agentes_sesiones_activas():
    agentes_activos_service = EstadoAgentesService()
    agentes = list(agentes_activos_service._obtener_agentes_activos_ami())
    sips_agentes = []
    for agente in agentes:
        if agente['status'] != 'OFFLINE':
            sips_agentes.append(int(agente['sip']))
    return sips_agentes


class AddSettingsContextMixin(object):

    def get_context_data(self, *args, **kwargs):
        context = super(AddSettingsContextMixin, self).get_context_data(*args, **kwargs)
        context['KAMAILIO_HOSTNAME'] = settings.KAMAILIO_HOSTNAME
        context['NGINX_HOSTNAME'] = settings.NGINX_HOSTNAME
        context['EXTERNAL_PORT'] = settings.OML_EXTERNAL_PORT
        return context
