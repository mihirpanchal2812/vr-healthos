from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('api/dashboard/', views.dashboard_data, name='dashboard_data'),

    # Patients
    path('patients/', views.patients_list, name='patients'),
    path('patients/<int:pk>/', views.patient_profile, name='patient_profile'),
    path('api/patients/create/', views.patient_create, name='patient_create'),
    path('api/patients/<int:pk>/update/', views.patient_update, name='patient_update'),
    path('api/patients/<int:pk>/delete/', views.patient_delete, name='patient_delete'),
    path('api/patients/check-phone/', views.patient_check_phone, name='patient_check_phone'),
    path('api/patients/search/', views.patient_search, name='patient_search'),

    # Appointments
    path('appointments/', views.appointments_view, name='appointments'),
    path('api/appointments/create/', views.appointment_create, name='appointment_create'),
    path('api/appointments/<int:pk>/update/', views.appointment_update, name='appointment_update'),
    path('api/appointments/<int:pk>/delete/', views.appointment_delete, name='appointment_delete'),
    path('api/appointments/calendar/', views.appointment_calendar_data, name='appointment_calendar_data'),
    path('api/appointments/booked-slots/', views.booked_slots, name='booked_slots'),

    # Billing
    path('billing/', views.billing_view, name='billing'),
    path('api/invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('api/invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('api/invoices/<int:pk>/collect/', views.collect_payment, name='collect_payment'),
    path('api/invoices/<int:pk>/update/', views.invoice_update, name='invoice_update'),

    # Documents
    path('api/documents/upload/', views.document_upload, name='document_upload'),
    path('api/documents/<int:pk>/delete/', views.document_delete, name='document_delete'),

    # Reminders
    path('reminders/', views.reminders_view, name='reminders'),

    # Logs
    path('logs/', views.logs_view, name='logs'),

    # Staff
    path('staff/', views.staff_view, name='staff'),
    path('api/staff/create/', views.staff_create, name='staff_create'),
    path('api/staff/<int:pk>/toggle/', views.staff_toggle, name='staff_toggle'),
    path('api/staff/<int:pk>/delete/', views.staff_delete, name='staff_delete'),

    # Finance (Admin)
    path('finance/', views.finance_view, name='finance'),
    path('api/finance/data/', views.finance_data, name='finance_data'),
    path('api/finance/export-pdf/', views.financial_report_pdf, name='financial_report_pdf'),
    path('api/finance/export-excel/', views.finance_excel_export, name='finance_excel_export'),
]
