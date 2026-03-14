from django.core.management.base import BaseCommand
from core.models import User, Patient, Appointment, Invoice, Log
from datetime import date, time
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed demo data for VR HealthOS'

    def handle(self, *args, **options):
        self.stdout.write('Seeding VR HealthOS...')

        # Users
        if not User.objects.filter(username='admin@hospital.com').exists():
            admin = User.objects.create_user(
                username='admin@hospital.com',
                email='admin@hospital.com',
                password='admin123',
                first_name='Dr. Sarah',
                last_name='Wilson',
                role='admin',
            )
            self.stdout.write(f'  Created admin: {admin.email}')

        if not User.objects.filter(username='reception@hospital.com').exists():
            staff = User.objects.create_user(
                username='reception@hospital.com',
                email='reception@hospital.com',
                password='staff123',
                first_name='Emily',
                last_name='Johnson',
                role='receptionist',
            )
            self.stdout.write(f'  Created staff: {staff.email}')

        admin_user = User.objects.get(username='admin@hospital.com')
        staff_user = User.objects.get(username='reception@hospital.com')

        # Extra staff
        extras = [
            ('michael@hospital.com', 'Michael', 'Brown', 'receptionist'),
            ('lisa@hospital.com', 'Lisa', 'Chen', 'receptionist'),
        ]
        for email, first, last, role in extras:
            if not User.objects.filter(username=email).exists():
                u = User.objects.create_user(
                    username=email, email=email, password='staff123',
                    first_name=first, last_name=last, role=role,
                )
                if email == 'lisa@hospital.com':
                    u.is_active = False
                    u.save()

        # Patients
        patients_data = [
            ('Rajesh Kumar', '+91 98765 43210', '12 MG Road, Mumbai', 45, 'Male'),
            ('Priya Sharma', '+91 87654 32109', '45 Park Street, Delhi', 32, 'Female'),
            ('Amit Patel', '+91 76543 21098', '78 Lake View, Bangalore', 58, 'Male'),
            ('Sneha Reddy', '+91 65432 10987', '23 Hill Road, Hyderabad', 28, 'Female'),
            ('Mohammed Ali', '+91 54321 09876', '56 Marine Drive, Chennai', 67, 'Male'),
            ('Anita Desai', '+91 43210 98765', '89 Gandhi Nagar, Pune', 41, 'Female'),
        ]
        for name, phone, addr, age, gender in patients_data:
            if not Patient.objects.filter(phone=phone).exists():
                Patient.objects.create(
                    full_name=name, phone=phone, address=addr, age=age, gender=gender
                )
                self.stdout.write(f'  Created patient: {name}')

        # Appointments
        today = date.today()
        appts_data = [
            ('Rajesh Kumar', today.replace(day=max(1, today.day - 1)), '09:00', 'Old Case', 300, 0, 'Cash', 'Paid', 'Follow-up checkup'),
            ('Priya Sharma', today.replace(day=max(1, today.day - 1)), '10:00', 'New Case', 700, 0, '', 'Pending', 'Initial consultation'),
            ('Amit Patel', today, '11:00', 'Old Case', 300, 0, 'Online', 'Paid', 'Lab results review'),
            ('Sneha Reddy', today, '14:00', 'New Case', 500, 0, '', 'Pending', 'Skin consultation'),
            ('Mohammed Ali', today.replace(day=min(28, today.day + 2)), '09:30', 'Old Case', 300, 150, 'Cash', 'Paid', 'BP monitoring'),
        ]

        for name, appt_date, t, vtype, base, extra, method, status, notes in appts_data:
            patient = Patient.objects.get(full_name=name)
            hour, minute = map(int, t.split(':'))
            ts = time(hour, minute)
            if not Appointment.objects.filter(date=appt_date, time_slot=ts).exists():
                appt = Appointment.objects.create(
                    patient=patient, date=appt_date, time_slot=ts,
                    visit_type=vtype, base_cost=Decimal(base), extra_cost=Decimal(extra),
                    payment_method=method, payment_status=status, notes=notes,
                )
                Invoice.objects.create(
                    appointment=appt, patient=patient,
                    base_cost=Decimal(base), extra_cost=Decimal(extra),
                    total_amount=appt.total_cost,
                    payment_method=method, payment_status=status,
                )
                self.stdout.write(f'  Created appointment: {name} on {appt_date}')

        # Logs
        if Log.objects.count() == 0:
            Log.objects.create(user=staff_user, action='Created patient', record_type='Patient', record_id='p6')
            Log.objects.create(user=staff_user, action='Booked appointment', record_type='Appointment', record_id='a5')
            Log.objects.create(user=admin_user, action='Updated patient record', record_type='Patient', record_id='p3')
            Log.objects.create(user=staff_user, action='Generated invoice', record_type='Invoice', record_id='inv4')
            Log.objects.create(user=staff_user, action='Uploaded document', record_type='Document', record_id='d1')
            Log.objects.create(user=admin_user, action='Viewed logs', record_type='System', record_id='-')

        self.stdout.write(self.style.SUCCESS('Seeding complete!'))
