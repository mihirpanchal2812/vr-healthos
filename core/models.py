from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import datetime


class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('receptionist', 'Receptionist'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='receptionist')

    def is_admin(self):
        return self.role == 'admin'

    def is_receptionist(self):
        return self.role == 'receptionist'

    class Meta:
        db_table = 'users'


class Patient(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]
    patient_id = models.CharField(max_length=10, unique=True, editable=False)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True, default='')
    age = models.IntegerField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    created_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.patient_id:
            last = Patient.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.patient_id = f'VRP-{next_num:05d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.patient_id} - {self.full_name}'

    class Meta:
        db_table = 'patients'
        ordering = ['-created_date']


class Appointment(models.Model):
    VISIT_TYPE_CHOICES = [
        ('Old Case', 'Old Case'),
        ('New Case', 'New Case'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('', '—'),
        ('Cash', 'Cash'),
        ('Online', 'Online'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateField()
    time_slot = models.TimeField()
    visit_type = models.CharField(max_length=20, choices=VISIT_TYPE_CHOICES, default='Old Case')
    base_cost = models.DecimalField(max_digits=10, decimal_places=2, default=300)
    extra_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, default='')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total_cost = self.base_cost + self.extra_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.patient.full_name} - {self.date} {self.time_slot}'

    class Meta:
        db_table = 'appointments'
        ordering = ['-date', '-time_slot']
        unique_together = ['date', 'time_slot']


class Invoice(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
    ]
    invoice_id = models.CharField(max_length=20, unique=True, editable=False)
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='invoice')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='invoices')
    base_cost = models.DecimalField(max_digits=10, decimal_places=2)
    extra_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, blank=True, default='')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    created_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_id:
            year = timezone.now().year
            last = Invoice.objects.filter(invoice_id__startswith=f'INV-{year}').order_by('-id').first()
            if last:
                last_num = int(last.invoice_id.split('-')[-1])
                next_num = last_num + 1
            else:
                next_num = 1
            self.invoice_id = f'INV-{year}-{next_num:03d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_id

    class Meta:
        db_table = 'invoices'
        ordering = ['-created_date']


class Document(models.Model):
    DOC_TYPE_CHOICES = [
        ('Prescription', 'Prescription'),
        ('Lab Report', 'Lab Report'),
        ('Medical Record', 'Medical Record'),
        ('Other', 'Other'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='documents/%Y/%m/')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES, default='Other')
    file_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.file_name and self.file:
            self.file_name = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.patient.full_name} - {self.file_name}'

    class Meta:
        db_table = 'documents'
        ordering = ['-uploaded_at']


class Log(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='logs')
    action = models.CharField(max_length=200)
    record_type = models.CharField(max_length=50)
    record_id = models.CharField(max_length=50, blank=True, default='-')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user} - {self.action} - {self.timestamp}'

    class Meta:
        db_table = 'logs'
        ordering = ['-timestamp']
