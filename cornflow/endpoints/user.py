"""
Endpoints for the user profiles
"""

# Import from libraries
from flask_apispec.views import MethodResource
from flask_apispec import marshal_with, use_kwargs, doc
from flask import current_app
import logging as log

# Import from internal modules
from .meta_resource import MetaResource
from ..models import UserModel, UserRoleModel
from ..schemas.user import (
    UserSchema,
    UserEndpointResponse,
    UserDetailsEndpointResponse,
    UserEditRequest,
)

from ..shared.authentication import Auth
from ..shared.const import ADMIN_ROLE, AUTH_LDAP
from ..shared.exceptions import (
    InvalidUsage,
    ObjectDoesNotExist,
    NoPermission,
    EndpointNotImplemented,
)
from ..shared.utils import db


# Initialize the schema that the endpoint uses
user_schema = UserSchema()


class UserEndpoint(MetaResource, MethodResource):
    """
    Endpoint with a get method which gives back all the info related to the users.
    Including their instances and executions
    """

    ROLES_WITH_ACCESS = [ADMIN_ROLE]

    @doc(description="Get all users", tags=["Users"])
    @Auth.auth_required
    @marshal_with(UserEndpointResponse(many=True))
    def get(self):
        """
        API (GET) method to get all the info from all the users
        It requires authentication to be passed in the form of a token that has to be linked to
        an existing session (login) made by the superuser

        :return: A dictionary with the user data and an integer with the HTTP status code
        :rtype: Tuple(dict, integer)
        """
        users = UserModel.get_all_users()
        return users, 200


# TODO: the PUT method here could be used to change the password of the user.
#   These endpoints could be used mainly by the cornflow webserver UI.
class UserDetailsEndpoint(MetaResource, MethodResource):
    """
    Endpoint use to get the information of one single user
    """

    @doc(description="Get a user", tags=["Users"])
    @Auth.auth_required
    @marshal_with(UserDetailsEndpointResponse)
    def get(self, user_id):
        """

        :param int user_id: User id.
        :return:
        :rtype: Tuple(dict, integer)
        """
        if self.get_user_id() != user_id and not self.is_admin():
            raise InvalidUsage(
                error="You have no permission to access given user", status_code=400
            )
        user_obj = UserModel.get_one_user(user_id)
        if user_obj is None:
            raise InvalidUsage(error="The object does not exist", status_code=404)
        return user_obj, 200

    @doc(description="Delete a user", tags=["Users"])
    @Auth.auth_required
    def delete(self, user_id):
        """

        :param int user_id: User id.
        :return:
        :rtype: Tuple(dict, integer)
        """
        if self.get_user_id() != user_id and not self.is_admin():
            raise NoPermission()
        user_obj = UserModel.get_one_user(user_id)
        if user_obj is None:
            raise ObjectDoesNotExist()
        # Service user can not be deleted
        if user_obj.is_service_user():
            raise NoPermission()
        user_obj.delete()
        log.info("User {} was deleted by user {}".format(user_id, self.get_user_id()))
        return {"message": "The object has been deleted"}, 200

    @doc(description="Edit a user", tags=["Users"])
    @Auth.auth_required
    @marshal_with(UserDetailsEndpointResponse)
    @use_kwargs(UserEditRequest, location="json")
    def put(self, user_id, **data):
        """
        API method to edit an existing user.
        It requires authentication to be passed in the form of a token that has to be linked to
        an existing session (login) made by a user. Only admin and superadmin can edit other users.

        :param int user_id: id of the user
        :return: A dictionary with a message (error if authentication failed, or the execution does not exist or
          a message) and an integer with the HTTP status code.
        :rtype: Tuple(dict, integer)
        """
        if self.get_user_id() != user_id and not self.is_admin():
            raise NoPermission()
        user_obj = UserModel.get_one_user(user_id)
        if user_obj is None:
            raise ObjectDoesNotExist()
        # in ldap-mode, users cannot be edited.
        if current_app.config["AUTH_TYPE"] == AUTH_LDAP and user_obj.comes_from_ldap():
            raise EndpointNotImplemented("To edit a user, go to LDAP server")
        user_obj.update(data)
        user_obj.save()
        log.info("User {} was edited by user {}".format(user_id, self.get_user_id()))
        return user_obj, 200


class ToggleUserAdmin(MetaResource, MethodResource):
    ROLES_WITH_ACCESS = [ADMIN_ROLE]

    @doc(description="Toggle user into admin", tags=["Users"])
    @Auth.auth_required
    @marshal_with(UserEndpointResponse)
    def put(self, user_id, make_admin):
        """
        API method to make admin or take out privileges.
        It requires authentication to be passed in the form of a token that has to be linked to
        an existing session (login) made by a user. Only superadmin can change this.

        :param int user_id: id of the user
        :param make_admin: 0 if the user is not going to be made admin, 1 if the user has to be made admin
        :return: A dictionary with a message (error if authentication failed, or the execution does not exist or
          a message) and an integer with the HTTP status code.
        :rtype: Tuple(dict, integer)
        """
        user_obj = UserModel.get_one_user(user_id)
        if user_obj is None:
            raise ObjectDoesNotExist()
        if make_admin:
            UserRoleModel(data={"user_id": user_id, "role_id": ADMIN_ROLE}).save()
        else:
            UserRoleModel.query.filter_by(user_id=user_id, role_id=ADMIN_ROLE).delete()
            db.session.commit()

        return user_obj, 200
