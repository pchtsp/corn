from marshmallow import fields, Schema
from .instance import InstanceSchema


class UserSchema(Schema):
    """ """

    id = fields.Int(dump_only=True)
    first_name = fields.Str()
    last_name = fields.Str()
    username = fields.Str(required=True)
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)
    created_at = fields.DateTime(dump_only=True)
    modified_at = fields.DateTime(dump_only=True)
    instances = fields.Nested(InstanceSchema, many=True)


class UserEndpointResponse(Schema):
    id = fields.Int()
    username = fields.Str()
    first_name = fields.Str()
    last_name = fields.Str()
    email = fields.Str()
    created_at = fields.Str()


class UserDetailsEndpointResponse(Schema):
    id = fields.Int()
    first_name = fields.Str()
    last_name = fields.Str()
    username = fields.Str()
    email = fields.Str()


class LoginEndpointRequest(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)


class UserEditRequest(Schema):
    username = fields.Str(required=False)
    first_name = fields.Str(required=False)
    last_name = fields.Str(required=False)
    email = fields.Str(required=False)
    password = fields.Str(required=False)


class UserSignupRequest(Schema):
    username = fields.Str(required=True)
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)
    first_name = fields.Str(required=False)
    last_name = fields.Str(required=False)
