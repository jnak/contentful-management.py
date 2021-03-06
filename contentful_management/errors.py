"""
contentful_management.errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module implements the Error classes.

API reference: https://www.contentful.com/developers/docs/references/content-delivery-api/#/introduction/errors

:copyright: (c) 2018 by Contentful GmbH.
:license: MIT, see LICENSE for more details.
"""


class HTTPError(Exception):
    """
    Base HTTP error class.
    """

    def __init__(self, response):
        self.response = response
        self.status_code = response.status_code

        message = self._best_available_message(response)
        super(HTTPError, self).__init__(message)

    def _default_error_message(self):
        return "The following error was received: {0}".format(self.response.text)

    def _handle_details(self, details):
        return "{0}".format(details)

    def _has_additional_error_info(self):
        return False

    def _additional_error_info(self):
        return []

    def _best_available_message(self, response):
        from .utils import json_error_class

        response_json = None
        error_message = [
          "HTTP status code: {0}".format(self.status_code),
        ]
        try:
            response_json = response.json()

            message = response_json.get('message', None)
            details = response_json.get('details', None)
            request_id = response_json.get('requestId', None)

            if message is not None:
                error_message.append("Message: {0}".format(message))
            else:
                error_message.append("Message: {0}".format(self._default_error_message()))
            if details is not None:
                error_message.append("Details: {0}".format(self._handle_details(details)))
            if request_id is not None:
                error_message.append("Request ID: {0}".format(request_id))
        except json_error_class():
            error_message.append("Message: {0}".format(self._default_error_message()))

        if self._has_additional_error_info():
            error_message += self._additional_error_info()

        return "\n".join(error_message)


class BadRequestError(HTTPError):
    """
    400
    """

    def _default_error_message(self):
        return "The request was malformed or missing a required parameter."

    def _handle_details(self, details):
        from .utils import string_class
        if isinstance(details, string_class()):
            return details

        def _handle_detail(detail):
            if isinstance(detail, string_class()):
                return detail
            return detail.get('details', None)

        if 'errors' in details:
            inner_details = [_handle_detail(detail) for detail in details['errors']]
            inner_details = [detail for detail in inner_details if detail is not None]  # This works in both Py2 and Py3
            return "\n\t".join(inner_details)

        return str(details)


class UnauthorizedError(HTTPError):
    """
    401
    """

    def _default_error_message(self):
        return "The authorization token was invalid."


class AccessDeniedError(HTTPError):
    """
    403
    """

    def _default_error_message(self):
        return "The specified token does not have access to the requested resource."

    def _handle_details(self, details):
        return "\n\tReasons:\n\t\t{0}".format("\n\t\t".join(details['reasons']))


class NotFoundError(HTTPError):
    """
    404
    """

    def _default_error_message(self):
        return "The requested resource or endpoint could not be found."

    def _handle_details(self, details):
        from .utils import string_class
        if isinstance(details, string_class()):
            return details

        message = "The requested {0} could not be found.".format(details['type'])
        resource_id = details.get('id', None)
        if resource_id is not None:
            message += " ID: {0}.".format(resource_id)

        return message


class VersionMismatchError(HTTPError):
    """
    409
    """
    def _default_error_message(self):
        return 'Version mismatch error. The version you specified was incorrect. This may be due to someone else editing the content.'


class UnprocessableEntityError(HTTPError):
    """
    422
    """
    def _default_error_message(self):
        return 'The resource you sent in the body is invalid.'

    def _handle_error(self, error):
        message = ''
        if 'name' in error and 'path' in error:
            message = "\t* Name: {0} - Path: '{1}'".format(
                error['name'],
                error['path']
            )
        else:
            message = self._default_error_message()

        if 'value' in error:
            message = "{0} - Value: '{1}'".format(
                message,
                error['value']
            )

        return message

    def _handle_details(self, details):
        errors = []

        for error in details['errors']:
            errors.append(self._handle_error(error))

        return '\n{0}'.format('\n'.join(errors))


class RateLimitExceededError(HTTPError):
    """
    429
    """

    RATE_LIMIT_RESET_HEADER_KEY = 'x-contentful-ratelimit-reset'

    def _has_reset_time(self):
        return self.RATE_LIMIT_RESET_HEADER_KEY in self.response.headers

    def reset_time(self):
        """Returns the reset time in seconds until next available request."""

        return int(self.response.headers[
            self.RATE_LIMIT_RESET_HEADER_KEY
        ])

    def _has_additional_error_info(self):
        return self._has_reset_time()

    def _additional_error_info(self):
        return ["Time until reset (seconds): {0}".format(self.reset_time())]

    def _default_error_message(self):
        return "Rate limit exceeded. Too many requests."


class ServerError(HTTPError):
    """
    500
    """

    def _default_error_message(self):
        return "Internal server error."


class BadGatewayError(HTTPError):
    """
    502
    """

    def _default_error_message(self):
        return "The requested space is hibernated."


class ServiceUnavailableError(HTTPError):
    """
    503
    """

    def _default_error_message(self):
        return "The request was malformed or missing a required parameter."


def get_error(response):
    """
    Gets Error by HTTP status code.
    """

    errors = {
        400: BadRequestError,
        401: UnauthorizedError,
        403: AccessDeniedError,
        404: NotFoundError,
        409: VersionMismatchError,
        422: UnprocessableEntityError,
        429: RateLimitExceededError,
        500: ServerError,
        502: BadGatewayError,
        503: ServiceUnavailableError
    }

    error_class = HTTPError
    if response.status_code in errors:
        error_class = errors[response.status_code]

    return error_class(response)
