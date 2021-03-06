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

"""Aca se encuentran las vistas con la creacion de los formularios dinamico en la
caso de que califica como gestion(que generalmente vulgarmente llamada venta)"""

from __future__ import unicode_literals

from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import (
    ListView, CreateView, DeleteView, FormView, View
)
from django.views.generic.edit import BaseUpdateView
from django.utils.translation import ugettext as _

from ominicontacto_app.models import Formulario, FieldFormulario
from ominicontacto_app.forms import (
    FormularioForm, FieldFormularioForm, OrdenCamposForm, FormularioCRMForm
)
from ominicontacto_app.services.campos_formulario import (
    OrdenCamposCampanaService
)
import logging as logging_

logger = logging_.getLogger(__name__)


class FormularioCreateView(CreateView):
    """Vista para crear el fomulario"""
    model = Formulario
    form_class = FormularioForm
    template_name = 'formulario/formulario_create_update_form.html'

    def get_success_url(self):
        return reverse('formulario_field',
                       kwargs={"pk_formulario": self.object.pk}
                       )


class FormularioListView(ListView):
    """Vista para listar los formularios"""
    template_name = 'formulario/formulario_list.html'
    model = Formulario


class FormularioMostrarOcultosView(FormularioListView):
    """Muestra tambi??n los formularios ocultos
    """

    def get_context_data(self, **kwargs):
        context = super(FormularioMostrarOcultosView, self).get_context_data(**kwargs)
        context['mostrar_ocultos'] = True
        return context


class FieldFormularioCreateView(CreateView):
    """Vista para crear un campo del formulario"""
    model = FieldFormulario
    template_name = 'formulario/formulario_field.html'
    context_object_name = 'fieldformulario'
    form_class = FieldFormularioForm

    def get_initial(self):
        initial = super(FieldFormularioCreateView, self).get_initial()
        formulario = Formulario.objects.get(pk=self.kwargs['pk_formulario'])
        initial.update({'formulario': formulario.id})
        return initial

    def get_context_data(self, **kwargs):
        context = super(
            FieldFormularioCreateView, self).get_context_data(**kwargs)
        formulario = Formulario.objects.get(pk=self.kwargs['pk_formulario'])
        context['formulario'] = formulario
        context['ORDEN_SENTIDO_UP'] = FieldFormulario.ORDEN_SENTIDO_UP
        context['ORDEN_SENTIDO_DOWN'] = FieldFormulario.ORDEN_SENTIDO_DOWN
        form_orden_campos = OrdenCamposForm()
        context['form_orden_campos'] = form_orden_campos
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.orden = \
            FieldFormulario.objects.obtener_siguiente_orden(
                self.kwargs['pk_formulario'])
        self.object.save()
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        message = _('<strong>Operaci??n Err??nea!</strong> ') + \
            _('No se pudo llevar a cabo la creacion de campo.')
        messages.add_message(
            self.request,
            messages.ERROR,
            message,
        )
        return super(FieldFormularioCreateView, self).form_invalid(form)

    def get_success_url(self):
        return reverse('formulario_field',
                       kwargs={"pk_formulario": self.kwargs['pk_formulario']}
                       )


class FieldFormularioOrdenView(BaseUpdateView):
    """
    Esta vista actualiza el orden de los campos del formulario.
    """

    model = FieldFormulario

    def get_initial(self):
        initial = super(FieldFormularioOrdenView, self).get_initial()
        formulario = Formulario.objects.get(pk=self.kwargs['pk_formulario'])
        initial.update({'formulario': formulario.id})
        return initial

    def get(self, request, *args, **kwargs):
        return self.redirecciona_a_campos_formulario()

    def form_valid(self, form_orden_campos):
        sentido_orden = int(form_orden_campos.cleaned_data.get(
                            'sentido_orden'))

        orden_campos_campana_service = OrdenCamposCampanaService()
        if sentido_orden == FieldFormulario.ORDEN_SENTIDO_UP:
            orden_campos_campana_service.baja_campo_una_posicion(
                self.get_object())
        elif sentido_orden == FieldFormulario.ORDEN_SENTIDO_DOWN:
            orden_campos_campana_service.sube_campo_una_posicion(
                self.get_object())
        else:
            return self.form_invalid(form_orden_campos)

        message = _('<strong>Operaci??n Exitosa!</strong> '
                    'Se llev?? a cabo con ??xito el reordenamiento de los campos.')
        messages.add_message(
            self.request,
            messages.SUCCESS,
            message,
        )
        return self.redirecciona_a_campos_formulario()

    def form_invalid(self, form_orden_campos):
        message = _('<strong>Operaci??n Err??nea!</strong> '
                    'No se pudo llevar a cabo el reordenamiento de los campos.')
        messages.add_message(
            self.request,
            messages.ERROR,
            message,
        )
        return self.redirecciona_a_campos_formulario()

    def post(self, request, *args, **kwargs):

        form_orden_campos = OrdenCamposForm(request.POST)

        if form_orden_campos.is_valid():
            return self.form_valid(form_orden_campos)
        else:
            return self.form_invalid(form_orden_campos)

    def redirecciona_a_campos_formulario(self):
        url = reverse('formulario_field',
                      kwargs={"pk_formulario": self.kwargs['pk_formulario']})
        return HttpResponseRedirect(url)


class FieldFormularioDeleteView(DeleteView):
    """
    Esta vista se encarga de la eliminaci??n del
    objeto FieldFormulario seleccionado.
    """

    model = FieldFormulario
    template_name = 'formulario/elimina_field_formulario.html'

    def delete(self, request, *args, **kwargs):
        message = '<strong>Operaci??n Exitosa!</strong>\
            Se llev?? a cabo con ??xito la eliminaci??n del field.'

        messages.add_message(
            self.request,
            messages.SUCCESS,
            message,
        )
        return super(FieldFormularioDeleteView, self).delete(request, *args,
                                                             **kwargs)

    def get_success_url(self):
        return reverse('formulario_field',
                       kwargs={"pk_formulario": self.kwargs['pk_formulario']}
                       )


class FormularioPreviewFormView(FormView):
    """Vista para ver el formulario una vez finalizado"""
    form_class = FormularioCRMForm
    template_name = 'formulario/formulario_preview.html'

    def dispatch(self, *args, **kwargs):
        formulario = Formulario.objects.get(pk=self.kwargs['pk_formulario'])
        campos = formulario.campos.all()

        if not campos.exists():
            message = _("No est?? permitido crear un formulario vacio.")
            messages.error(self.request, message)
            return redirect(reverse('formulario_field',
                                    kwargs={"pk_formulario": self.kwargs['pk_formulario']}))
        return super(FormularioPreviewFormView, self).dispatch(*args, **kwargs)

    def get_form(self):
        self.form_class = self.get_form_class()
        formulario = Formulario.objects.get(pk=self.kwargs['pk_formulario'])
        campos = formulario.campos.all()
        return self.form_class(campos=campos, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super(
            FormularioPreviewFormView, self).get_context_data(**kwargs)
        context['pk_formulario'] = self.kwargs['pk_formulario']
        return context


class FormularioVistaFormView(FormView):
    """Vista para visualizar el fomulario en una vista previa"""
    form_class = FormularioCRMForm
    template_name = 'formulario/formulario_vista.html'

    def get_form(self):
        self.form_class = self.get_form_class()
        formulario = Formulario.objects.get(pk=self.kwargs['pk_formulario'])
        campos = formulario.campos.all()
        return self.form_class(campos=campos, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super(
            FormularioVistaFormView, self).get_context_data(**kwargs)
        context['pk_formulario'] = self.kwargs['pk_formulario']
        return context


# class FormularioCreateFormView(FormView):
#     form_class = FormularioCRMForm
#     template_name = 'formulario/formulario_create.html'

#     def get_form(self):
#         self.form_class = self.get_form_class()
#         formulario = Formulario.objects.get(pk=self.kwargs['pk_formulario'])
#         campos = formulario.campos.all()
#         return self.form_class(campos=campos, **self.get_form_kwargs())

#     def get_context_data(self, **kwargs):
#         context = super(
#             FormularioCreateFormView, self).get_context_data(**kwargs)
#         context['pk_formulario'] = self.kwargs['pk_formulario']
#         campana = Campana.objects.get(pk=self.kwargs['pk_campana'])
#         contacto = Contacto.objects.get(pk=self.kwargs['pk_contacto'])
#         bd_contacto = campana.bd_contacto
#         nombres = bd_contacto.get_metadata().nombres_de_columnas[2:]
#         datos = json.loads(contacto.datos)
#         mas_datos = []
#         for nombre, dato in zip(nombres, datos):
#             mas_datos.append((nombre, dato))
#         context['contacto'] = contacto
#         context['mas_datos'] = mas_datos

#         return context

#     def form_valid(self, form):
#         campana = Campana.objects.get(pk=self.kwargs['pk_campana'])
#         agente = AgenteProfile.objects.get(pk=self.kwargs['id_agente'])
#         contacto = Contacto.objects.get(pk=self.kwargs['pk_contacto'])
#         metadata = json.dumps(form.cleaned_data)
#         RespuestaFormularioGestion.objects.create(campana=campana, agente=agente,
#                                        contacto=contacto, metadata=metadata)
#         return HttpResponseRedirect('/blanco/')

#     def get_success_url(self):
#         reverse('view_blanco')


class FormularioDeleteView(DeleteView):
    """
    Esta vista se encarga de la eliminaci??n de un contacto
    """
    model = Formulario
    template_name = 'formulario/formulario_eliminar.html'

    def dispatch(self, request, *args, **kwargs):
        formulario = self.get_object()

        if formulario.opcioncalificacion_set.all().exists():
            message = _("No est?? permitido eliminar un formulario asignado a alguna campa??a")
            messages.error(self.request, message)
            return HttpResponseRedirect(
                reverse('formulario_list'))
        return super(FormularioDeleteView, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return Formulario.objects.get(pk=self.kwargs['pk_formulario'])

    def get_success_url(self):
        return reverse('formulario_list')


class FormularioMostrarOcultarView(View):
    """Vista que se encarga de cambiar el atributo 'oculto' de un formulario
    negando su valor actual
    """

    def post(self, request, *args, **kwargs):
        pk = kwargs.get('pk_formulario')
        formulario = get_object_or_404(Formulario, pk=pk)
        formulario.oculto = not formulario.oculto
        formulario.save()
        return JsonResponse({'status': 'OK', 'oculto': formulario.oculto})
