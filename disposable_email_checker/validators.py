# -*- coding: utf-8 -*-

import re
from six.moves import range
from django.conf import settings
from django.utils.encoding import force_text
from django.core import validators
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from bdea.client import BDEAClient

# Django moved the location of `get_callable` in Django 2.0. We have kept the original import for
# backwards compatibility.
try:
    from django.core.urlresolvers import get_callable
except ImportError:
    from django.urls import get_callable


class DisposableEmailChecker():
    """
    Check if an email is from a disposable email service
    """

    message = _('Blocked email provider.')
    code = 'invalid'
    whitelist = []

    def __init__(self, message=None, code=None, whitelist=None):
        if message is not None:
            self.message = message
        elif hasattr(settings, 'BDEA_MESSAGE'):
            self.message = getattr(settings, 'BDEA_MESSAGE')
        if code is not None:
            self.code = code
        if whitelist is not None:
            self.whitelist = whitelist

        self.emails = self._load_emails()
        self.BDEA_APIKEY = getattr(settings, 'BDEA_APIKEY', None)
        self.BDEA_TIMEOUT = getattr(settings, 'BDEA_TIMEOUT', 5)

    def __call__(self, value):
        value = force_text(value)

        # Catch invalid emails before we check if they're disposable
        try:
            validators.validate_email(value)
        except ValidationError:
            return

        user_part, domain_part = value.rsplit('@', 1)

        if domain_part not in self.whitelist:
            if self.BDEA_APIKEY:  # Validate using block-disposable-email.com
                client = BDEAClient(self.BDEA_APIKEY, timeout=self.BDEA_TIMEOUT)
                response = client.get_domain_status(domain_part)

                if response.status() and response.is_disposable():
                    raise ValidationError(self.message, code=self.code)

            """
            This will run if we are not using BDEA, we're out of BDEA credits,
            there was an error contacting BDEA's servers or we did not get a
            hit on BDEA. Basically always check using local list as a backup
            """
            for email_group in self.chunk(self.emails, 20):
                # regex = "(.*" + "$)|(.*".join(email_group) + "$)"
                # if re.match(regex, value):
                if domain_part in email_group:
                    raise ValidationError(self.message, code=self.code)

    def _load_emails(self):
        loader = getattr(
            settings, 'DEC_LOADER', 'disposable_email_checker.emails.email_domain_loader'
        )
        return get_callable(loader)()

    def chunk(self, l, n):
        return (l[i:i+n] for i in range(0, len(l), n))

validate_disposable_email = DisposableEmailChecker()
