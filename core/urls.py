from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    # PWA: el service worker debe servirse desde la raiz para tener alcance total
    path('sw.js', TemplateView.as_view(
        template_name='sw.js', content_type='application/javascript',
    ), name='sw'),

    # Auth
    path('login/', auth_views.LoginView.as_view(
        template_name='auth/login.html', redirect_authenticated_user=True,
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', views.register_view, name='register'),

    # Usuario
    path('', views.home, name='home'),
    path('rutina/', views.routine_view, name='routine'),
    path('rutina/dia/<int:day>/', views.routine_view, name='routine_day'),
    path('rutina/item/<int:pk>/editar/', views.routine_item_edit, name='routine_item_edit'),
    path('rutina/item/<int:pk>/check/', views.routine_item_check, name='routine_item_check'),
    path('rutina/item/<int:pk>/eliminar/', views.routine_item_delete, name='routine_item_delete'),
    path('catalogo/', views.catalog, name='catalog'),
    path('ejercicio/<int:pk>/agregar/', views.exercise_add, name='exercise_add'),
    path('entrenar/registrar/', views.log_today, name='log_today'),
    path('historial/', views.history, name='history'),
    path('progreso/<int:pk>/', views.progress, name='progress'),

    # Suscripcion y pagos
    path('suscripcion/', views.subscription, name='subscription'),
    path('pago/crear/', views.pay_create, name='pay_create'),
    path('pago/retorno/', views.pay_return, name='pay_return'),
    path('webhook/mercadopago/', views.mp_webhook, name='mp_webhook'),
    path('webhook/github/', views.github_webhook, name='github_webhook'),

    # Panel de administracion
    path('panel/', views.panel, name='panel'),
    path('panel/configuracion/', views.panel_config, name='panel_config'),
    path('panel/usuarios/<int:pk>/mes/', views.panel_user_add_month, name='panel_user_add_month'),
    path('panel/usuarios/<int:pk>/liberar/', views.panel_user_exempt, name='panel_user_exempt'),
    path('panel/categorias/', views.panel_categories, name='panel_categories'),
    path('panel/categorias/nueva/', views.panel_category_form, name='panel_category_create'),
    path('panel/categorias/<int:pk>/editar/', views.panel_category_form, name='panel_category_edit'),
    path('panel/categorias/<int:pk>/eliminar/', views.panel_category_delete, name='panel_category_delete'),
    path('panel/ejercicios/', views.panel_exercises, name='panel_exercises'),
    path('panel/ejercicios/nuevo/', views.panel_exercise_form, name='panel_exercise_create'),
    path('panel/ejercicios/<int:pk>/editar/', views.panel_exercise_form, name='panel_exercise_edit'),
    path('panel/ejercicios/<int:pk>/eliminar/', views.panel_exercise_delete, name='panel_exercise_delete'),
    path('panel/usuarios/', views.panel_users, name='panel_users'),
    path('panel/usuarios/<int:pk>/toggle/', views.panel_user_toggle, name='panel_user_toggle'),
    path('panel/usuarios/<int:pk>/eliminar/', views.panel_user_delete, name='panel_user_delete'),
]
