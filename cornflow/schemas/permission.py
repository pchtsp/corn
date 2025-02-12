"""
This file contains the schemas used for the endpoints that manage the permissions on views by roles
"""

# Imports from marshmallow library
from marshmallow import fields, Schema


class PermissionViewRoleResponse(Schema):
    """
    Schema used for the get methods
    """

    id = fields.Int()
    action_id = fields.Int()
    action = fields.Function(lambda obj: obj.action.name.replace("_", " "))
    api_view_id = fields.Int()
    api_view = fields.Function(lambda obj: obj.api_view.name)
    role_id = fields.Int()
    role = fields.Function(lambda obj: obj.role.name)
