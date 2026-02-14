from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib.messages import get_messages
from Sapp.app.user import create_associate_user, associateuser
from Sapp.app.company import Company

class CreateAssociateTest(TestCase):
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass'
        )
        self.company = Company.objects.create(
            company_name="Test Company",
            company_email="test@company.com"
        )
    
    def test_create_associate_user_function(self):
        """Test the create_associate_user function directly"""
        test_data = {
            'username': 'testassociate',
            'email': 'test@associate.com',
            'first_name': 'Test',
            'last_name': 'Associate',
            'password': 'testpass123',
            'associate_id': 'ASSOC001',
            'mobile': '1234567890',
            'address': 'Test Address',
            'companies': [self.company]
        }
        
        # Call the function
        associate = create_associate_user(**test_data)
        
        # Verify results
        self.assertIsNotNone(associate)
        self.assertEqual(associate.associate_id, 'ASSOC001')
        self.assertEqual(associate.user.username, 'testassociate')
        self.assertEqual(associate.mobile, '1234567890')
        self.assertTrue(associate.is_active)
        
        # Check company association
        self.assertIn(self.company, associate.get_companies())
    
    def test_create_associate_view_success(self):
        """Test successful associate creation via view"""
        self.client.login(username='admin', password='adminpass')
        
        post_data = {
            'username': 'viewtestassociate',
            'email': 'viewtest@associate.com',
            'first_name': 'ViewTest',
            'last_name': 'Associate',
            'password1': 'viewtestpass123',
            'password2': 'viewtestpass123',
            'associate_id': 'VASSOC001',
            'mobile': '9876543210',
            'address': 'View Test Address',
            'companies': [self.company.id]
        }
        
        response = self.client.post(reverse('create_associate'), post_data)
        
        # Check if associate was created
        self.assertTrue(associateuser.objects.filter(associate_id='VASSOC001').exists())
        
        # Check redirect (success should redirect to list_associates)
        self.assertEqual(response.status_code, 302)
    
    def test_create_associate_view_password_mismatch(self):
        """Test password mismatch error"""
        self.client.login(username='admin', password='adminpass')
        
        post_data = {
            'username': 'testuser',
            'password1': 'pass123',
            'password2': 'pass456',  # Different password
            'associate_id': 'ASSOC002',
            'email': 'test@test.com',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        response = self.client.post(reverse('create_associate'), post_data)
        
        # Should not create associate
        self.assertFalse(associateuser.objects.filter(associate_id='ASSOC002').exists())
        
        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Passwords do not match' in str(m) for m in messages))
    
    def test_create_associate_view_duplicate_username(self):
        """Test duplicate username error"""
        # Create existing user
        User.objects.create_user(username='existinguser', password='pass123')
        
        self.client.login(username='admin', password='adminpass')
        
        post_data = {
            'username': 'existinguser',  # Duplicate username
            'password1': 'pass123',
            'password2': 'pass123',
            'associate_id': 'ASSOC003',
            'email': 'test@test.com',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        response = self.client.post(reverse('create_associate'), post_data)
        
        # Should not create associate
        self.assertFalse(associateuser.objects.filter(associate_id='ASSOC003').exists())
        
        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Username already exists' in str(m) for m in messages))