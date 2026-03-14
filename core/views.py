import json
import io
import calendar
import math
from datetime import datetime, date, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, KeepTogether, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics import renderPDF

from .models import User, Patient, Appointment, Invoice, Document, Log


# ─── Helpers ──────────────────────────────────────────────

def log_action(user, action, record_type, record_id='-'):
    Log.objects.create(user=user, action=action, record_type=record_type, record_id=str(record_id))


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'admin':
            return JsonResponse({'error': 'Admin access required'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── Auth ─────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = ''
    if request.method == 'POST':
        email = request.POST.get('email', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            log_action(user, 'Logged in', 'System')
            return redirect('dashboard')
        else:
            error = 'Invalid credentials'
    return render(request, 'login.html', {'error': error})


def logout_view(request):
    if request.user.is_authenticated:
        log_action(request.user, 'Logged out', 'System')
    logout(request)
    return redirect('login')


# ─── Dashboard ────────────────────────────────────────────

@login_required
def dashboard(request):
    today = date.today()
    total_patients = Patient.objects.count()
    total_appointments = Appointment.objects.count()
    total_invoices = Invoice.objects.count()
    total_revenue = Invoice.objects.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0
    todays_appointments = Appointment.objects.filter(date=today).select_related('patient')

    context = {
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'total_invoices': total_invoices,
        'total_revenue': total_revenue,
        'todays_appointments': todays_appointments,
        'page': 'dashboard',
    }
    return render(request, 'dashboard.html', context)


@login_required
def dashboard_data(request):
    today = date.today()
    months = []
    patient_counts = []
    revenue_counts = []

    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 30)
        month_start = d.replace(day=1)
        if d.month == 12:
            month_end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)

        months.append(d.strftime('%b'))
        patient_counts.append(
            Appointment.objects.filter(date__gte=month_start, date__lte=month_end).count()
        )
        revenue_counts.append(
            float(Invoice.objects.filter(
                payment_status='Paid',
                created_date__date__gte=month_start,
                created_date__date__lte=month_end
            ).aggregate(s=Sum('total_amount'))['s'] or 0)
        )

    old_cases = Appointment.objects.filter(visit_type='Old Case').count()
    new_cases = Appointment.objects.filter(visit_type='New Case').count()

    return JsonResponse({
        'months': months,
        'patients': patient_counts,
        'revenue': revenue_counts,
        'visit_types': {'old': old_cases, 'new': new_cases},
    })


# ─── Patients ─────────────────────────────────────────────

@login_required
def patients_list(request):
    q = request.GET.get('q', '')
    patients = Patient.objects.all()
    if q:
        patients = patients.filter(
            Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(patient_id__icontains=q)
        )
    return render(request, 'patients.html', {'patients': patients, 'q': q, 'page': 'patients'})


@login_required
def patient_profile(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    appointments = patient.appointments.all()
    invoices = patient.invoices.all()
    documents = patient.documents.all()
    return render(request, 'patient_profile.html', {
        'patient': patient,
        'appointments': appointments,
        'invoices': invoices,
        'documents': documents,
        'page': 'patients',
    })


@login_required
def patient_search(request):
    q = request.GET.get('q', '')
    patients = Patient.objects.filter(
        Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(patient_id__icontains=q)
    )[:10]
    data = [{'id': p.id, 'patient_id': p.patient_id, 'full_name': p.full_name, 'phone': p.phone} for p in patients]
    return JsonResponse(data, safe=False)


@login_required
@require_POST
def patient_check_phone(request):
    phone = request.POST.get('phone', '')
    try:
        patient = Patient.objects.get(phone=phone)
        return JsonResponse({
            'exists': True,
            'patient': {
                'id': patient.id,
                'patient_id': patient.patient_id,
                'full_name': patient.full_name,
                'phone': patient.phone,
                'age': patient.age,
                'gender': patient.gender,
                'address': patient.address,
            }
        })
    except Patient.DoesNotExist:
        return JsonResponse({'exists': False})


@login_required
@require_POST
def patient_create(request):
    try:
        data = request.POST
        phone = data.get('phone', '').strip()
        if Patient.objects.filter(phone=phone).exists():
            return JsonResponse({'success': False, 'error': 'Profile with this number already registered'}, status=400)

        patient = Patient.objects.create(
            full_name=data['full_name'],
            phone=phone,
            address=data.get('address', ''),
            age=int(data['age']),
            gender=data['gender'],
        )
        log_action(request.user, 'Created patient', 'Patient', patient.patient_id)
        return JsonResponse({
            'success': True,
            'patient': {
                'id': patient.id,
                'patient_id': patient.patient_id,
                'full_name': patient.full_name,
                'phone': patient.phone,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def patient_update(request, pk):
    """Update an existing patient."""
    try:
        patient = get_object_or_404(Patient, pk=pk)
        data = request.POST
        patient.full_name = data.get('full_name', patient.full_name)
        new_phone = data.get('phone', patient.phone).strip()
        if new_phone != patient.phone and Patient.objects.filter(phone=new_phone).exists():
            return JsonResponse({'success': False, 'error': 'Profile with this number already registered'}, status=400)
        patient.phone = new_phone
        patient.address = data.get('address', patient.address)
        patient.age = int(data.get('age', patient.age))
        patient.gender = data.get('gender', patient.gender)
        patient.save()
        log_action(request.user, 'Updated patient', 'Patient', patient.patient_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def patient_delete(request, pk):
    """Delete a patient — admin only."""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Admin access required'}, status=403)
    try:
        patient = get_object_or_404(Patient, pk=pk)
        patient_id = patient.patient_id
        patient.delete()
        log_action(request.user, 'Deleted patient', 'Patient', patient_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ─── Documents ────────────────────────────────────────

@login_required
@require_POST
def document_delete(request, pk):
    """Delete a document."""
    try:
        doc = get_object_or_404(Document, pk=pk)
        doc_id = doc.id
        doc.file.delete(save=False)
        doc.delete()
        log_action(request.user, 'Deleted document', 'Document', doc_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ─── Appointments ─────────────────────────────────────────

@login_required
def appointments_view(request):
    appointments = Appointment.objects.select_related('patient').all()
    patients = Patient.objects.all()
    return render(request, 'appointments.html', {
        'appointments': appointments,
        'patients': patients,
        'page': 'appointments',
    })


@login_required
def appointment_calendar_data(request):
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))
    appts = Appointment.objects.filter(date__year=year, date__month=month).select_related('patient')
    data = []
    for a in appts:
        data.append({
            'id': a.id,
            'date': a.date.isoformat(),
            'time': a.time_slot.strftime('%H:%M'),
            'patient_name': a.patient.full_name,
            'visit_type': a.visit_type,
            'total_cost': float(a.total_cost),
            'payment_status': a.payment_status,
        })
    return JsonResponse(data, safe=False)


@login_required
def booked_slots(request):
    appt_date = request.GET.get('date', '')
    exclude_id = request.GET.get('exclude', '')
    if not appt_date:
        return JsonResponse([], safe=False)
    slots = Appointment.objects.filter(date=appt_date)
    if exclude_id:
        slots = slots.exclude(id=int(exclude_id))
    data = [a.time_slot.strftime('%H:%M') for a in slots]
    return JsonResponse(data, safe=False)


@login_required
@require_POST
def appointment_create(request):
    try:
        data = request.POST
        patient = Patient.objects.get(id=data['patient_id'])
        appt_date = data['date']
        time_slot = data['time_slot']

        # Check conflict
        if Appointment.objects.filter(date=appt_date, time_slot=time_slot).exists():
            return JsonResponse({'success': False, 'error': 'Time slot already booked'}, status=400)

        base_cost = Decimal(data.get('base_cost', '300'))
        extra_cost = Decimal(data.get('extra_cost', '0'))

        appointment = Appointment.objects.create(
            patient=patient,
            date=appt_date,
            time_slot=time_slot,
            visit_type=data.get('visit_type', 'Old Case'),
            base_cost=base_cost,
            extra_cost=extra_cost,
            payment_method=data.get('payment_method', ''),
            payment_status=data.get('payment_status', 'Pending'),
            notes=data.get('notes', ''),
        )

        # Auto-generate invoice
        Invoice.objects.create(
            appointment=appointment,
            patient=patient,
            base_cost=base_cost,
            extra_cost=extra_cost,
            total_amount=appointment.total_cost,
            payment_method=appointment.payment_method,
            payment_status=appointment.payment_status,
        )

        log_action(request.user, 'Booked appointment', 'Appointment', appointment.id)
        return JsonResponse({'success': True, 'id': appointment.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def appointment_update(request, pk):
    try:
        appt = get_object_or_404(Appointment, pk=pk)
        data = request.POST

        new_date = data.get('date', appt.date)
        new_time = data.get('time_slot', appt.time_slot)

        # Check conflict (exclude self)
        conflict = Appointment.objects.filter(date=new_date, time_slot=new_time).exclude(pk=pk).exists()
        if conflict:
            return JsonResponse({'success': False, 'error': 'Time slot already booked'}, status=400)

        appt.date = new_date
        appt.time_slot = new_time
        appt.visit_type = data.get('visit_type', appt.visit_type)
        appt.base_cost = Decimal(data.get('base_cost', str(appt.base_cost)))
        appt.extra_cost = Decimal(data.get('extra_cost', str(appt.extra_cost)))
        appt.payment_method = data.get('payment_method', appt.payment_method)
        appt.payment_status = data.get('payment_status', appt.payment_status)
        appt.notes = data.get('notes', appt.notes)
        appt.save()

        # Update invoice
        if hasattr(appt, 'invoice'):
            inv = appt.invoice
            inv.base_cost = appt.base_cost
            inv.extra_cost = appt.extra_cost
            inv.total_amount = appt.total_cost
            inv.payment_method = appt.payment_method
            inv.payment_status = appt.payment_status
            inv.save()

        log_action(request.user, 'Modified appointment', 'Appointment', appt.id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def appointment_delete(request, pk):
    try:
        appt = get_object_or_404(Appointment, pk=pk)
        appt_id = appt.id
        appt.delete()
        log_action(request.user, 'Deleted appointment', 'Appointment', appt_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ─── Billing ──────────────────────────────────────────────

@login_required
def billing_view(request):
    invoices = Invoice.objects.select_related('patient', 'appointment').all()

    filter_type = request.GET.get('filter', 'all')
    filter_date = request.GET.get('date', '')
    filter_patient = request.GET.get('patient', '')

    if filter_type == 'today':
        invoices = invoices.filter(created_date__date=date.today())
    elif filter_type == 'date' and filter_date:
        invoices = invoices.filter(created_date__date=filter_date)
    elif filter_type == 'patient' and filter_patient:
        invoices = invoices.filter(
            Q(patient__full_name__icontains=filter_patient) |
            Q(patient__patient_id__icontains=filter_patient)
        )

    total_revenue = invoices.aggregate(s=Sum('total_amount'))['s'] or 0
    collected = invoices.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0
    pending = invoices.filter(payment_status='Pending').aggregate(s=Sum('total_amount'))['s'] or 0

    context = {
        'invoices': invoices,
        'total_revenue': total_revenue,
        'collected': collected,
        'pending': pending,
        'filter_type': filter_type,
        'filter_date': filter_date,
        'filter_patient': filter_patient,
        'page': 'billing',
    }
    return render(request, 'billing.html', context)


@login_required
def invoice_detail(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)
    return JsonResponse({
        'invoice_id': inv.invoice_id,
        'patient_name': inv.patient.full_name,
        'patient_id': inv.patient.patient_id,
        'patient_phone': inv.patient.phone,
        'date': inv.appointment.date.isoformat(),
        'visit_type': inv.appointment.visit_type,
        'base_cost': float(inv.base_cost),
        'extra_cost': float(inv.extra_cost),
        'total_amount': float(inv.total_amount),
        'payment_method': inv.payment_method or '—',
        'payment_status': inv.payment_status,
    })


@login_required
@require_POST
def collect_payment(request, pk):
    try:
        inv = get_object_or_404(Invoice, pk=pk)
        method = request.POST.get('payment_method', 'Cash')
        inv.payment_method = method
        inv.payment_status = 'Paid'
        inv.save()

        # Update appointment too
        appt = inv.appointment
        appt.payment_method = method
        appt.payment_status = 'Paid'
        appt.save()

        log_action(request.user, f'Collected payment ({method})', 'Invoice', inv.invoice_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def invoice_update(request, pk):
    """Update invoice payment method and/or status inline."""
    try:
        inv = get_object_or_404(Invoice, pk=pk)
        data = request.POST
        new_method = data.get('payment_method', None)
        new_status = data.get('payment_status', None)

        if new_method is not None:
            inv.payment_method = new_method
        if new_status is not None:
            inv.payment_status = new_status
        inv.save()

        # Sync appointment
        appt = inv.appointment
        if new_method is not None:
            appt.payment_method = new_method
        if new_status is not None:
            appt.payment_status = new_status
        appt.save()

        log_action(request.user, f'Updated invoice {inv.invoice_id}', 'Invoice', inv.invoice_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def invoice_pdf(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#1e40af'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    normal = styles['Normal']
    bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontName='Helvetica-Bold')

    elements = []

    # Header
    elements.append(Paragraph('VR HealthOS', title_style))
    elements.append(Paragraph('Hospital Management System', subtitle_style))
    elements.append(Spacer(1, 5*mm))

    # Invoice info
    inv_info = [
        [Paragraph(f'<b>Invoice:</b> {inv.invoice_id}', normal),
         Paragraph(f'<b>Date:</b> {inv.appointment.date}', normal)],
    ]
    t = Table(inv_info, colWidths=[90*mm, 80*mm])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(t)
    elements.append(Spacer(1, 5*mm))

    # Patient info
    elements.append(Paragraph('<b>Bill To:</b>', normal))
    elements.append(Paragraph(f'{inv.patient.full_name}', bold_style))
    elements.append(Paragraph(f'{inv.patient.phone}', normal))
    elements.append(Paragraph(f'ID: {inv.patient.patient_id}', normal))
    elements.append(Spacer(1, 8*mm))

    # Items table
    data = [
        ['Description', 'Amount'],
        [f'Consultation ({inv.appointment.visit_type})', f'₹{inv.base_cost}'],
    ]
    if inv.extra_cost > 0:
        data.append(['Extra Charges', f'₹{inv.extra_cost}'])
    data.append(['', ''])
    data.append(['Total', f'₹{inv.total_amount}'])

    t = Table(data, colWidths=[120*mm, 50*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#e2e8f0')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8*mm))

    # Payment status
    status_text = f'<b>Status:</b> {inv.payment_status}'
    if inv.payment_method:
        status_text += f'  |  <b>Paid via:</b> {inv.payment_method}'
    elements.append(Paragraph(status_text, normal))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{inv.invoice_id}.pdf"'
    return response


# ─── Documents ────────────────────────────────────────────

@login_required
@require_POST
def document_upload(request):
    try:
        patient = get_object_or_404(Patient, id=request.POST['patient_id'])
        file = request.FILES['file']
        doc = Document.objects.create(
            patient=patient,
            file=file,
            doc_type=request.POST.get('doc_type', 'Other'),
            uploaded_by=request.user,
            file_name=file.name,
        )
        log_action(request.user, 'Uploaded document', 'Document', doc.id)
        return JsonResponse({'success': True, 'id': doc.id, 'file_name': doc.file_name})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ─── Reminders ────────────────────────────────────────────

@login_required
def reminders_view(request):
    patients = Patient.objects.all()
    return render(request, 'reminders.html', {'patients': patients, 'page': 'reminders'})


# ─── Logs ─────────────────────────────────────────────────

@login_required
def logs_view(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    q = request.GET.get('q', '')
    logs = Log.objects.select_related('user').all()
    if q:
        logs = logs.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) |
            Q(action__icontains=q) | Q(record_type__icontains=q)
        )
    log_action(request.user, 'Viewed logs', 'System')
    return render(request, 'logs.html', {'logs': logs[:100], 'q': q, 'page': 'logs'})


# ─── Staff ────────────────────────────────────────────────

@login_required
def staff_view(request):
    if request.user.role != 'admin':
        return redirect('dashboard')
    staff = User.objects.all().order_by('-date_joined')
    return render(request, 'staff.html', {'staff': staff, 'page': 'staff'})


@login_required
@require_POST
def staff_create(request):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        data = request.POST
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            role=data.get('role', 'receptionist'),
        )
        log_action(request.user, f'Created staff account', 'Staff', user.id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def staff_toggle(request, pk):
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        user = get_object_or_404(User, pk=pk)
        user.is_active = not user.is_active
        user.save()
        action = 'Enabled' if user.is_active else 'Disabled'
        log_action(request.user, f'{action} staff account', 'Staff', user.id)
        return JsonResponse({'success': True, 'is_active': user.is_active})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def staff_delete(request, pk):
    """Delete staff account — admin only."""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            return JsonResponse({'success': False, 'error': 'Cannot delete your own account'}, status=400)
        uid = user.id
        user.delete()
        log_action(request.user, 'Deleted staff account', 'Staff', uid)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ─── Finance ──────────────────────────────────────────────

@login_required
def finance_view(request):
    """Render the Finance dashboard page (admin only)."""
    if request.user.role != 'admin':
        return redirect('dashboard')

    current_year = date.today().year
    selected_year = int(request.GET.get('year', current_year))
    selected_period = request.GET.get('period', 'monthly')

    # Generate year choices (current year ± 3)
    year_choices = list(range(current_year - 3, current_year + 2))

    # Calculate summary for selected year
    year_invoices = Invoice.objects.filter(created_date__year=selected_year)
    total_revenue = year_invoices.aggregate(s=Sum('total_amount'))['s'] or 0
    collected = year_invoices.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0
    outstanding = year_invoices.filter(payment_status='Pending').aggregate(s=Sum('total_amount'))['s'] or 0
    total_appointments = Appointment.objects.filter(date__year=selected_year).count()

    context = {
        'page': 'finance',
        'selected_year': selected_year,
        'selected_period': selected_period,
        'year_choices': year_choices,
        'total_revenue': total_revenue,
        'collected': collected,
        'outstanding': outstanding,
        'total_appointments': total_appointments,
    }
    return render(request, 'finance.html', context)


@login_required
def finance_data(request):
    """JSON API returning monthly financial data for charts."""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Forbidden'}, status=403)

    selected_year = int(request.GET.get('year', date.today().year))

    month_labels = []
    collected_data = []
    pending_data = []
    cash_data = []
    online_data = []

    for m in range(1, 13):
        month_labels.append(date(selected_year, m, 1).strftime('%b'))

        month_invoices = Invoice.objects.filter(created_date__year=selected_year, created_date__month=m)

        collected_amt = float(
            month_invoices.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0
        )
        pending_amt = float(
            month_invoices.filter(payment_status='Pending').aggregate(s=Sum('total_amount'))['s'] or 0
        )
        cash_amt = float(
            month_invoices.filter(payment_status='Paid', payment_method='Cash').aggregate(s=Sum('total_amount'))['s'] or 0
        )
        online_amt = float(
            month_invoices.filter(payment_status='Paid', payment_method='Online').aggregate(s=Sum('total_amount'))['s'] or 0
        )

        collected_data.append(collected_amt)
        pending_data.append(pending_amt)
        cash_data.append(cash_amt)
        online_data.append(online_amt)

    # Payment mode totals for pie chart
    total_cash = float(
        Invoice.objects.filter(
            created_date__year=selected_year, payment_status='Paid', payment_method='Cash'
        ).aggregate(s=Sum('total_amount'))['s'] or 0
    )
    total_online = float(
        Invoice.objects.filter(
            created_date__year=selected_year, payment_status='Paid', payment_method='Online'
        ).aggregate(s=Sum('total_amount'))['s'] or 0
    )
    total_pending_mode = float(
        Invoice.objects.filter(
            created_date__year=selected_year, payment_status='Pending'
        ).aggregate(s=Sum('total_amount'))['s'] or 0
    )

    return JsonResponse({
        'months': month_labels,
        'collected': collected_data,
        'pending': pending_data,
        'cash': cash_data,
        'online': online_data,
        'mode_split': {
            'cash': total_cash,
            'online': total_online,
            'pending': total_pending_mode,
        },
    })


@login_required
def finance_excel_export(request):
    """Export financial data as a CSV file (Excel-compatible)."""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Forbidden'}, status=403)

    selected_year = int(request.GET.get('year', date.today().year))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="HealthOS_Finance_{selected_year}.csv"'
    response.write('\ufeff')  # BOM for Excel UTF-8

    import csv
    writer = csv.writer(response)

    # Header
    writer.writerow(['VR HealthOS — Financial Report'])
    writer.writerow([f'Year: {selected_year}', f'Generated: {date.today().strftime("%d %B %Y")}'])
    writer.writerow([])

    # Summary
    year_invoices = Invoice.objects.filter(created_date__year=selected_year)
    total_revenue = year_invoices.aggregate(s=Sum('total_amount'))['s'] or 0
    collected = year_invoices.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0
    outstanding = year_invoices.filter(payment_status='Pending').aggregate(s=Sum('total_amount'))['s'] or 0
    total_appointments = Appointment.objects.filter(date__year=selected_year).count()

    writer.writerow(['Summary'])
    writer.writerow(['Total Revenue', f'{total_revenue}'])
    writer.writerow(['Collected', f'{collected}'])
    writer.writerow(['Outstanding', f'{outstanding}'])
    writer.writerow(['Total Appointments', f'{total_appointments}'])
    writer.writerow([])

    # Monthly breakdown
    writer.writerow(['Monthly Breakdown'])
    writer.writerow(['Month', 'Collected', 'Pending', 'Cash', 'Online', 'Appointments'])
    for m in range(1, 13):
        month_name = date(selected_year, m, 1).strftime('%B')
        month_invoices = Invoice.objects.filter(created_date__year=selected_year, created_date__month=m)
        month_appts = Appointment.objects.filter(date__year=selected_year, date__month=m).count()
        m_collected = month_invoices.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0
        m_pending = month_invoices.filter(payment_status='Pending').aggregate(s=Sum('total_amount'))['s'] or 0
        m_cash = month_invoices.filter(payment_status='Paid', payment_method='Cash').aggregate(s=Sum('total_amount'))['s'] or 0
        m_online = month_invoices.filter(payment_status='Paid', payment_method='Online').aggregate(s=Sum('total_amount'))['s'] or 0
        writer.writerow([month_name, f'{m_collected}', f'{m_pending}', f'{m_cash}', f'{m_online}', f'{month_appts}'])

    writer.writerow([])

    # Invoice detail
    writer.writerow(['Invoice Details'])
    writer.writerow(['Invoice ID', 'Patient', 'Date', 'Amount', 'Method', 'Status'])
    invoices = Invoice.objects.filter(
        created_date__year=selected_year
    ).select_related('patient', 'appointment').order_by('-created_date')
    for inv in invoices:
        writer.writerow([
            inv.invoice_id,
            inv.patient.full_name,
            inv.appointment.date.strftime('%Y-%m-%d'),
            f'{inv.total_amount}',
            inv.payment_method or '—',
            inv.payment_status,
        ])

    log_action(request.user, f'Exported finance Excel ({selected_year})', 'Report', '-')
    return response


# ─── Financial Report PDF ─────────────────────────────

@login_required
def financial_report_pdf(request):
    """Generate a comprehensive financial report PDF with charts and tables."""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Admin access required'}, status=403)

    today = date.today()
    selected_year = int(request.GET.get('year', today.year))
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=20*mm, bottomMargin=20*mm,
        leftMargin=15*mm, rightMargin=15*mm,
    )
    styles = getSampleStyleSheet()
    page_width = A4[0] - 30*mm

    title_style = ParagraphStyle('RTitle', parent=styles['Title'], fontSize=20,
                                  textColor=colors.HexColor('#1e40af'), spaceAfter=4)
    subtitle_style = ParagraphStyle('RSub', parent=styles['Normal'], fontSize=10,
                                     textColor=colors.grey, spaceAfter=12)
    section_style = ParagraphStyle('RSection', parent=styles['Heading2'], fontSize=14,
                                    textColor=colors.HexColor('#1e293b'), spaceBefore=16, spaceAfter=10)
    normal = styles['Normal']
    small_style = ParagraphStyle('RSmall', parent=normal, fontSize=9, textColor=colors.HexColor('#64748b'))

    elements = []

    # ── Page 1: Header & Summary ──
    elements.append(Paragraph(f'VR HealthOS — Financial Report ({selected_year})', title_style))
    elements.append(Paragraph(f'Generated on {today.strftime("%d %B %Y")}', subtitle_style))
    elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#e2e8f0'), spaceAfter=12))

    # Summary stats for selected year
    year_invoices = Invoice.objects.filter(created_date__year=selected_year)
    total_revenue = year_invoices.aggregate(s=Sum('total_amount'))['s'] or 0
    collected = year_invoices.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0
    outstanding = year_invoices.filter(payment_status='Pending').aggregate(s=Sum('total_amount'))['s'] or 0
    total_appointments = Appointment.objects.filter(date__year=selected_year).count()
    cash_revenue = year_invoices.filter(payment_status='Paid', payment_method='Cash').aggregate(s=Sum('total_amount'))['s'] or 0
    online_revenue = year_invoices.filter(payment_status='Paid', payment_method='Online').aggregate(s=Sum('total_amount'))['s'] or 0

    elements.append(Paragraph('Summary Overview', section_style))

    summary_data = [
        ['Metric', 'Value'],
        ['Total Revenue', f'₹{total_revenue}'],
        ['Collected', f'₹{collected}'],
        ['Outstanding', f'₹{outstanding}'],
        ['Total Appointments', str(total_appointments)],
        ['Cash Revenue', f'₹{cash_revenue}'],
        ['Online Revenue', f'₹{online_revenue}'],
    ]
    t = Table(summary_data, colWidths=[page_width * 0.5, page_width * 0.5])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12*mm))

    # ── Monthly Revenue Bar Chart ──
    elements.append(Paragraph(f'Monthly Revenue — {selected_year}', section_style))

    months = []
    collected_counts = []
    pending_counts = []
    cash_counts = []
    online_counts = []

    for m in range(1, 13):
        months.append(date(selected_year, m, 1).strftime('%b'))
        month_inv = Invoice.objects.filter(created_date__year=selected_year, created_date__month=m)
        collected_counts.append(float(month_inv.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0))
        pending_counts.append(float(month_inv.filter(payment_status='Pending').aggregate(s=Sum('total_amount'))['s'] or 0))
        cash_counts.append(float(month_inv.filter(payment_status='Paid', payment_method='Cash').aggregate(s=Sum('total_amount'))['s'] or 0))
        online_counts.append(float(month_inv.filter(payment_status='Paid', payment_method='Online').aggregate(s=Sum('total_amount'))['s'] or 0))

    chart_width = float(page_width)
    chart_height = 160
    bar_area_width = chart_width - 60

    # Draw collected vs pending bar chart
    drawing = Drawing(chart_width, chart_height + 40)
    max_val = max(max(collected_counts + pending_counts, default=1), 1)
    bar_group_width = bar_area_width / 12
    bar_width = bar_group_width * 0.3

    for i in range(5):
        y_val = (max_val / 4) * i
        y_pos = 30 + (chart_height / 4) * i
        drawing.add(String(0, y_pos, f'{int(y_val)}', fontSize=7, fillColor=colors.HexColor('#64748b')))
        drawing.add(Line(40, y_pos + 3, chart_width, y_pos + 3,
                         strokeColor=colors.HexColor('#e2e8f0'), strokeWidth=0.5))

    for idx in range(12):
        x = 50 + idx * bar_group_width
        h1 = (collected_counts[idx] / max_val) * chart_height if max_val > 0 else 0
        h2 = (pending_counts[idx] / max_val) * chart_height if max_val > 0 else 0
        drawing.add(Rect(x, 30, bar_width, h1,
                         fillColor=colors.HexColor('#10b981'), strokeColor=None))
        drawing.add(Rect(x + bar_width + 2, 30, bar_width, h2,
                         fillColor=colors.HexColor('#f59e0b'), strokeColor=None))
        drawing.add(String(x + bar_width * 0.5, 15, months[idx],
                           fontSize=7, fillColor=colors.HexColor('#64748b'), textAnchor='middle'))

    # Legend
    drawing.add(Rect(chart_width - 130, chart_height + 25, 10, 10,
                     fillColor=colors.HexColor('#10b981'), strokeColor=None))
    drawing.add(String(chart_width - 115, chart_height + 27, 'Collected',
                       fontSize=8, fillColor=colors.HexColor('#64748b')))
    drawing.add(Rect(chart_width - 55, chart_height + 25, 10, 10,
                     fillColor=colors.HexColor('#f59e0b'), strokeColor=None))
    drawing.add(String(chart_width - 40, chart_height + 27, 'Pending',
                       fontSize=8, fillColor=colors.HexColor('#64748b')))

    elements.append(drawing)
    elements.append(Spacer(1, 8*mm))

    # Monthly data table
    monthly_table_data = [['Month', 'Collected (₹)', 'Pending (₹)', 'Cash (₹)', 'Online (₹)']]
    for i in range(12):
        monthly_table_data.append([
            months[i],
            f'₹{collected_counts[i]:,.0f}',
            f'₹{pending_counts[i]:,.0f}',
            f'₹{cash_counts[i]:,.0f}',
            f'₹{online_counts[i]:,.0f}',
        ])

    t = Table(monthly_table_data, colWidths=[page_width/5]*5)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)

    # ── Page 2: Payment Breakdown + Cash vs Online Chart ──
    elements.append(PageBreak())

    # Payment mode pie approximation
    elements.append(Paragraph('Payment Mode Split', section_style))
    total_paid = float(cash_revenue) + float(online_revenue)
    if total_paid > 0:
        cash_pct = float(cash_revenue) / total_paid * 100
        online_pct = float(online_revenue) / total_paid * 100
    else:
        cash_pct = online_pct = 0

    pie_drawing = Drawing(chart_width, 80)
    bar_total_width = chart_width - 40
    if total_paid > 0:
        pie_drawing.add(Rect(20, 40, bar_total_width * (cash_pct / 100), 30,
                             fillColor=colors.HexColor('#10b981'), strokeColor=None))
        pie_drawing.add(Rect(20 + bar_total_width * (cash_pct / 100), 40,
                             bar_total_width * (online_pct / 100), 30,
                             fillColor=colors.HexColor('#3b82f6'), strokeColor=None))
    pie_drawing.add(String(20, 22, f'Cash: ₹{cash_revenue} ({cash_pct:.1f}%)',
                           fontSize=9, fillColor=colors.HexColor('#065f46')))
    pie_drawing.add(String(chart_width * 0.5, 22, f'Online: ₹{online_revenue} ({online_pct:.1f}%)',
                           fontSize=9, fillColor=colors.HexColor('#1e40af')))
    elements.append(pie_drawing)
    elements.append(Spacer(1, 8*mm))

    # Cash vs Online by month bar chart
    elements.append(Paragraph('Cash vs Online Payments by Month', section_style))
    co_drawing = Drawing(chart_width, chart_height + 40)
    max_co = max(max(cash_counts + online_counts, default=1), 1)

    for i in range(5):
        y_val = (max_co / 4) * i
        y_pos = 30 + (chart_height / 4) * i
        co_drawing.add(String(0, y_pos, f'{int(y_val)}', fontSize=7, fillColor=colors.HexColor('#64748b')))
        co_drawing.add(Line(40, y_pos + 3, chart_width, y_pos + 3,
                            strokeColor=colors.HexColor('#e2e8f0'), strokeWidth=0.5))

    for idx in range(12):
        x = 50 + idx * bar_group_width
        h1 = (cash_counts[idx] / max_co) * chart_height if max_co > 0 else 0
        h2 = (online_counts[idx] / max_co) * chart_height if max_co > 0 else 0
        co_drawing.add(Rect(x, 30, bar_width, h1,
                            fillColor=colors.HexColor('#10b981'), strokeColor=None))
        co_drawing.add(Rect(x + bar_width + 2, 30, bar_width, h2,
                            fillColor=colors.HexColor('#3b82f6'), strokeColor=None))
        co_drawing.add(String(x + bar_width * 0.5, 15, months[idx],
                              fontSize=7, fillColor=colors.HexColor('#64748b'), textAnchor='middle'))

    co_drawing.add(Rect(chart_width - 100, chart_height + 25, 10, 10,
                        fillColor=colors.HexColor('#10b981'), strokeColor=None))
    co_drawing.add(String(chart_width - 85, chart_height + 27, 'Cash',
                          fontSize=8, fillColor=colors.HexColor('#64748b')))
    co_drawing.add(Rect(chart_width - 45, chart_height + 25, 10, 10,
                        fillColor=colors.HexColor('#3b82f6'), strokeColor=None))
    co_drawing.add(String(chart_width - 30, chart_height + 27, 'Online',
                          fontSize=8, fillColor=colors.HexColor('#64748b')))
    elements.append(co_drawing)

    # ── Page 3: Invoice Listing ──
    elements.append(PageBreak())
    elements.append(Paragraph(f'Invoice Details — {selected_year}', section_style))

    recent_invoices = Invoice.objects.filter(
        created_date__year=selected_year
    ).select_related('patient', 'appointment').order_by('-created_date')[:60]

    inv_list = list(recent_invoices)
    chunk_size = 25
    for chunk_idx in range(0, len(inv_list), chunk_size):
        chunk = inv_list[chunk_idx:chunk_idx + chunk_size]
        inv_table_data = [['Invoice ID', 'Patient', 'Date', 'Amount', 'Method', 'Status']]
        for inv in chunk:
            inv_table_data.append([
                inv.invoice_id,
                Paragraph(inv.patient.full_name, small_style),
                inv.appointment.date.strftime('%Y-%m-%d'),
                f'₹{inv.total_amount}',
                inv.payment_method or '—',
                inv.payment_status,
            ])

        col_widths = [page_width*0.15, page_width*0.25, page_width*0.15,
                      page_width*0.15, page_width*0.15, page_width*0.15]
        t = Table(inv_table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('ALIGN', (4, 0), (5, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(KeepTogether([t]))
        if chunk_idx + chunk_size < len(inv_list):
            elements.append(PageBreak())
            elements.append(Paragraph(f'Invoice Details — {selected_year} (continued)', section_style))

    # Footer
    def add_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.HexColor('#64748b'))
        canvas_obj.drawString(15*mm, 12*mm, f'VR HealthOS — Financial Report {selected_year} — {today.strftime("%d/%m/%Y")}')
        canvas_obj.drawRightString(A4[0] - 15*mm, 12*mm, f'Page {doc_obj.page}')
        canvas_obj.restoreState()

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="HealthOS_Financial_Report_{selected_year}.pdf"'
    log_action(request.user, f'Downloaded financial report ({selected_year})', 'Report', '-')
    return response



