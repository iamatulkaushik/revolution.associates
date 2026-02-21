from django.forms import forms
from django.db import models
from django.shortcuts import render, redirect
from Sapp.app.user import User
from django.contrib.auth import authenticate

# Classes for Branch and Department models in the application. These models represent the structure of the database tables for branches and departments, including fields for branch and department details, as well as metadata for tracking creation and updates.

class branch(models.model):
    branchid = models.AutoField(primary_key=True)
    branch_name = models.CharField(max_length=255, db_column='Branch_Name', blank=False, null=False)
    branch_address = models.TextField()
    branch_email = models.EmailField()
    contact_person = models.CharField(max_length=200, blank=True, null=True)
    Cotact_mobile = models.CharField(max_length=10, blank=True, null=True)
    companyid = models.ForeignKey('Sapp.app.company', on_delete=models.CASCADE)

    created_by = models.ForeignKey(User, null=False, blank=False)
    updated_by = models.ForeignKey(User, blank=True, null=True)
    created_at = models.DateField(auto_now=True)
    updated_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f'{self.branch_name}'
    
    class Meta:
        db_table = 'branch_table'


class department(models.Model):
    departmentid = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=255, db_column='Department_Name', blank=False, null=False)
    branch = models.ForeignKey(branch, on_delete=models.CASCADE)
    companyid = models.ForeignKey('Sapp.app.company', on_delete=models.CASCADE) 
    created_by = models.ForeignKey(User, null=False, blank=False)
    updated_by = models.ForeignKey(User, blank=True, null=True)
    created_at = models.DateField(auto_now=True)
    updated_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f'{self.department_name}'
    
    class Meta:
        db_table = 'department_table'
        unique_together = ('department_name','branch')

# forms for Branch and Department models to handle user input and validation when creating or updating branch and department records in the application.

class branch_form(forms.ModelForm):
    class Meta:
        model = branch
        fields = ['branch_name', 'branch_address', 'branch_email', 'contact_person', 'Cotact_mobile']

class department_form(forms.ModelForm):
    class Meta:
        model = department
        fields = ['department_name', 'branch']


# Views for handling the creation and updating of branch and department records, including form validation and saving the data to the database.

class branch_view(forms.View):
    def get(self, request):
        form = branch_form()
        return render(request, 'branch_form.html', {'form': form}) 

    def post(self, request):
        form = branch_form(request.POST)
        if form.is_valid():
            branch_instance = form.save(commit=False)
            branch_instance.created_by = request.user
            branch_instance.save()
            return redirect('branch_list')
        return render(request, 'branch_form.html', {'form': form})
    
class department_view(forms.View):
    def get(self, request):
        form = department_form()
        return render(request, 'department_form.html', {'form': form})

    def post(self, request):
        form = department_form(request.POST)
        if form.is_valid():
            department_instance = form.save(commit=False)
            department_instance.created_by = request.user
            department_instance.save()
            return redirect('department_list')
        return render(request, 'department_form.html', {'form': form})
