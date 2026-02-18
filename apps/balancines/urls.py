# apps/balancines/urls.py
from django.urls import path, re_path
from django.contrib.auth import views as auth_views
from . import views
from .forms import LoginForm

urlpatterns = [
    # ========== PÁGINAS PRINCIPALES ==========
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # ========== AUTENTICACIÓN ==========
    path('login/',
         auth_views.LoginView.as_view(
             template_name='accounts/login.html',
             authentication_form=LoginForm,
             redirect_authenticated_user=True,
         ),
         name='login'),
    
    path('logout/',
         auth_views.LogoutView.as_view(
             template_name='accounts/logout.html',
             next_page='home'
         ),
         name='logout'),
    
    path('register/', views.register, name='register'),
    
    # ========== INVENTARIO - PRINCIPAL ==========
    path('inventario/', views.inventario_principal, name='inventario_principal'),
    path('inventario/dashboard/', views.dashboard_inventario, name='dashboard_inventario'),
    path('inventario/buscar/', views.buscar_inventario, name='buscar_inventario'),
    path('inventario/exportar-excel/', views.exportar_inventario_excel, name='exportar_inventario_excel'),
    
    # ========== INVENTARIO - TIPOS DE BALANCÍN ==========
    path('inventario/tipos-balancin/', views.lista_tipos_balancin, name='lista_tipos_balancin'),
    path('inventario/tipos-balancin/agregar/', views.agregar_tipo_balancin, name='agregar_tipo_balancin'),
    re_path(r'^inventario/tipos-balancin/(?P<codigo>.+)/$', views.detalle_tipo_balancin, name='detalle_tipo_balancin'),
    
    # ========== INVENTARIO - BALANCINES INDIVIDUALES ==========
    path('inventario/balancines/', views.lista_balancines_individuales, name='lista_balancines_individuales'),
    path('inventario/balancines/agregar/', views.agregar_balancin_individual, name='agregar_balancin_individual'),
    
    re_path(r'^inventario/balancines/(?P<codigo>.+)/registrar-oh/$', views.registrar_oh_balancin, name='registrar_oh_balancin'),
    re_path(r'^inventario/balancines/(?P<codigo>.+)/editar/$', views.editar_balancin_individual, name='editar_balancin_individual'),
    re_path(r'^inventario/balancines/(?P<codigo>.+)/eliminar/$', views.eliminar_balancin_individual, name='eliminar_balancin_individual'),
    re_path(r'^inventario/balancines/(?P<codigo>.+)/$', views.detalle_balancin, name='detalle_balancin'),
    
    # ========== API PARA CÓDIGOS DE BALANCINES ==========
    path('api/ultimo-codigo-balancin/', views.ultimo_codigo_balancin, name='ultimo_codigo_balancin'),
    
    # ========== DASHBOARD OH ==========
    path('inventario/dashboard-oh/', views.dashboard_oh_nuevo, name='dashboard_oh_balancines'),
    path('inventario/dashboard-oh-nuevo/', views.dashboard_oh_nuevo, name='dashboard_oh_nuevo'),
    
    # ========== NUEVA URL PARA AGREGAR OH ==========
    path('inventario/registrar_oh_balancin/', views.registrar_oh_balancin, name='registrar_oh_balancin'),  # ← AGREGAR ESTA LÍNEA
    
    # ========== INVENTARIO - REPUESTOS PARA BALANCINES ==========
    path('inventario/repuestos-balancin/', views.lista_repuestos_balancin, name='lista_repuestos_balancin'),
    path('inventario/repuestos-balancin/agregar/', views.agregar_repuesto_balancin, name='agregar_repuesto_balancin'),
    path('inventario/repuestos-balancin/<str:item>/entrada/', views.entrada_stock_balancin, name='entrada_stock_balancin'),
    path('inventario/repuestos-balancin/<str:item>/salida/', views.salida_stock_balancin, name='salida_stock_balancin'),    
    
    # ========== EXPORTAR DATOS ==========
    path('inventario/exportar-oh-excel/', views.exportar_oh_excel, name='exportar_oh_excel'),
    
    # ========== INVENTARIO - REPUESTOS ADICIONALES ==========
    path('inventario/repuestos-adicionales/', views.lista_repuestos_adicionales, name='lista_repuestos_adicionales'),
    path('inventario/repuestos-adicionales/agregar/', views.agregar_repuesto_adicional, name='agregar_repuesto_adicional'),
    path('inventario/repuestos-adicionales/<str:item>/entrada/', views.entrada_stock_adicional, name='entrada_stock_adicional'),
    path('inventario/repuestos-adicionales/<str:item>/salida/', views.salida_stock_adicional, name='salida_stock_adicional'),
]