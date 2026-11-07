import re
from rest_framework import serializers


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (str, int)) or not re.fullmatch(r'-?\d+', str(data)):
            self.fail('invalid')
        return super().to_internal_value(data)


def integer(value, minimum=1, maximum=2147483647):
    return StrictIntegerField(min_value=minimum, max_value=maximum).run_validation(value)


def boolean(value):
    return serializers.BooleanField().run_validation(value)
