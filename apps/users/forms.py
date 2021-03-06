import re

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, forms as auth_forms

from tower import ugettext as _, ugettext_lazy as _lazy

from users.models import Profile


USERNAME_INVALID = _lazy(u'Username may contain only letters, '
                         'numbers and @/./+/-/_ characters.')
# See bug 643759
USERNAME_INVALID_2 = _lazy(u'Username may contain only letters, '
                            'numbers and ./+/-/_ characters.')
USERNAME_REQUIRED = _lazy(u'Please enter a username.')
USERNAME_SHORT = _lazy(u'Username is too short (%(show_value)s characters). '
                       'It must be at least %(limit_value)s characters.')
USERNAME_LONG = _lazy(u'Username is too long (%(show_value)s characters). '
                      'It must be %(limit_value)s characters or less.')
EMAIL_INVALID = _lazy(u'Please enter a valid email address.')
EMAIL_REQUIRED = _lazy(u'Please enter an email address.')
PASSWD_REQUIRED = _lazy(u'Please enter a valid password.')
PASSWD2_REQUIRED = _lazy(u'Please enter your password twice.')
PASSWD_SHORT = _lazy(u'Password is too short '
                      '(At least %(limit_value)s characters).')
PASSWD_CURRENT = _lazy(u'Please enter your current password.')


PASSWD_MIN_LENGTH = 8


class RegisterForm(forms.ModelForm):
    """A user registration form that detects duplicate email addresses.

    The default Django user creation form does not require email addresses
    to be unique. This form does, and sets a minimum length
    for usernames.
    """
    username = forms.RegexField(max_length=30, min_length=4,
        regex=r'^[\w.+-]+$',
        error_messages={'invalid': USERNAME_INVALID_2,
                        'required': USERNAME_REQUIRED,
                        'min_length': USERNAME_SHORT,
                        'max_length': USERNAME_LONG})
    password = forms.CharField(error_messages={'required': PASSWD_REQUIRED,
                                               'min_length': PASSWD_SHORT},
                                               min_length=PASSWD_MIN_LENGTH)
    password2 = forms.CharField(error_messages={'required': PASSWD2_REQUIRED})
    email = forms.EmailField(error_messages={'required': EMAIL_REQUIRED,
                                             'invalid': EMAIL_INVALID})
    newsletter = forms.BooleanField(required=False)
    spark_newsletter = forms.BooleanField(required=False)

    class Meta(object):
        model = User
        fields = ('username', 'password', 'password2', 'email')

    def clean(self):
        super(RegisterForm, self).clean()
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if self.is_valid() and not password == password2:
            raise forms.ValidationError(_('Passwords do not match.'))

        return self.cleaned_data

    def clean_email(self):
        email = self.cleaned_data['email']
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError(_('Email address already in use.'))
        return email

    def __init__(self,  request=None, *args, **kwargs):
        super(RegisterForm, self).__init__(request, auto_id='id_for_%s',
                                           *args, **kwargs)


class AuthenticationForm(auth_forms.AuthenticationForm):
    """ Redefines AuthenticationForm to provide a new error message
        when authentication has failed. 
    """
    username = forms.CharField(error_messages={'invalid': USERNAME_INVALID_2,
                                            'required': USERNAME_REQUIRED})
    password = forms.CharField(error_messages={'required': PASSWD_REQUIRED})

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
           self.user_cache = authenticate(username=username,
                                          password=password)
           if self.user_cache is None:
               raise forms.ValidationError(
                   _("Oops! Your username or password doesn't match our records. Please try again."))
           elif not self.user_cache.is_active:
               raise forms.ValidationError(_('This account is inactive.'))

        if self.request:
           if not self.request.session.test_cookie_worked():
               raise forms.ValidationError(
                   _("Your Web browser doesn't appear to have cookies "
                     "enabled. Cookies are required for logging in."))

        return self.cleaned_data


class PasswordResetForm(auth_forms.PasswordResetForm):
    """ Redefines PasswordResetForm to customize validation and error messages.
    """
    email = forms.CharField(error_messages={'required': EMAIL_REQUIRED})
    
    def clean_email(self):
        try:
            super(PasswordResetForm, self).clean_email()
        except forms.ValidationError, e:
            # Don't leak existence of email addresses 
            # (No error if wrong email address)
            pass
        
        return self.cleaned_data


class EmailConfirmationForm(forms.Form):
    """This form validates that the user has entered his current email address.
    
       It is used by desktop and mobile websites for password recovery.
    """
    email = forms.EmailField(error_messages={'required': EMAIL_REQUIRED,
                                             'invalid': EMAIL_INVALID})

    def __init__(self, user, *args, **kwargs):
        super(EmailConfirmationForm, self).__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = self.cleaned_data['email']
        if self.user.email != email:
            # No need to localize this error message because the user won't see it.
            raise forms.ValidationError('Bad email address')

        return email


class EmailChangeForm(forms.Form):
    """A simple form that requires a password and an email address.
    
    It validates that it's the correct password for the current user and that it is not 
    the current user's email.
    """
    password = forms.CharField(error_messages={'required': PASSWD_CURRENT})
    new_email = forms.EmailField(error_messages={'required': EMAIL_REQUIRED,
                                                 'invalid': EMAIL_INVALID})
    confirm_new_email = forms.EmailField(error_messages={'required': EMAIL_REQUIRED,
                                                         'invalid': EMAIL_INVALID})

    def __init__(self, user, *args, **kwargs):
        super(EmailChangeForm, self).__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        password = self.cleaned_data.get('password')
        new_email = self.cleaned_data.get('new_email')
        confirm_new_email = self.cleaned_data.get('confirm_new_email')
        
        if not self.user.check_password(password):
            raise forms.ValidationError(PASSWD_CURRENT)
            
        if self.user.email == new_email:
            raise forms.ValidationError(_('This is your current email address.'))
        
        if new_email != confirm_new_email:
            raise forms.ValidationError(EMAIL_INVALID)
        
        if User.objects.filter(email=new_email).exists():
            raise forms.ValidationError(_('A user with that email address '
                                          'already exists.'))
        return self.cleaned_data


class PasswordChangeForm(auth_forms.PasswordChangeForm):
    """This form requires the current user's correct password 
       and two matching new password values."""
    old_password = forms.CharField(error_messages={'required': PASSWD_CURRENT})
    new_password1 = forms.CharField(error_messages={'required': PASSWD_REQUIRED,
                                                   'min_length': PASSWD_SHORT},
                                    min_length=PASSWD_MIN_LENGTH)
    new_password2 = forms.CharField(error_messages={'required': PASSWD2_REQUIRED,
                                                    'min_length': PASSWD_SHORT})
    
    def clean(self):
        super(PasswordChangeForm, self).clean()
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        if not new_password1 == new_password2:
            raise forms.ValidationError(_('Passwords must match.'))

        return self.cleaned_data
    
    def clean_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError(PASSWD_CURRENT)
        
        return old_password


class PasswordConfirmationForm(forms.Form):
    """A simple form that requires and validates the current user's password."""
    password = forms.CharField(error_messages={'required': PASSWD_CURRENT})
    
    def __init__(self, user, *args, **kwargs):
        super(PasswordConfirmationForm, self).__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.user.check_password(password):
            raise forms.ValidationError(PASSWD_CURRENT)
        
        return password


class SetPasswordForm(auth_forms.SetPasswordForm):
    """This form is used to change a user's password after he has followed
        a link to reset it.
    """
    new_password1 = forms.CharField(error_messages={'required': PASSWD_REQUIRED,
                                                    'min_length': PASSWD_SHORT},
                                    min_length=PASSWD_MIN_LENGTH)
    new_password2 = forms.CharField(error_messages={'required': PASSWD2_REQUIRED})
    
    def clean(self):
        super(SetPasswordForm, self).clean()
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        if new_password1 and new_password2 and not new_password1 == new_password2:
           raise forms.ValidationError(_('Passwords must match.'))

        return self.cleaned_data

