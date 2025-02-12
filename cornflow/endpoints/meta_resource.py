"""
Meta resource used in the endpoints to generalize the methods and how they work in order to make all endpoints the same.
It should allow all CRUD (create, read, update, delete) operations
"""
# Import from libraries
from flask import request
from flask_restful import Resource
from functools import wraps

# Import from internal modules
from ..shared.authentication import Auth
from ..shared.const import ALL_DEFAULT_ROLES
from ..shared.exceptions import InvalidUsage, ObjectDoesNotExist, NoPermission


class MetaResource(Resource):
    # method_decorators = [Auth.auth_required]
    ROLES_WITH_ACCESS = ALL_DEFAULT_ROLES
    DESCRIPTION = ""

    def __init__(self):
        super().__init__()
        self.user = None
        self.model = None
        self.query = None
        self.dependents = None
        self.foreign_data = None

    def get_user(self):
        """
        :return: a user of a request
        :rtype: UserModel
        """
        if self.user is None:
            self.user = Auth.get_user_obj_from_header(request.headers)
            if self.user is None:
                raise InvalidUsage("Error authenticating user")
        return self.user

    def get_user_id(self):
        """
        :return: the id of the user
        :rtype: int
        """
        return self.get_user().id

    def is_admin(self):
        """
        :return: if user is admin
        :rtype: bool
        """
        return self.get_user().is_admin()

    def is_service_user(self):
        """
        :return: if user is superadmin
        :rtype: bool
        """
        return self.get_user().is_service_user()

    @staticmethod
    def get_data_or_404(func):
        """
        Auth decorator
        :param func:
        :return:
        """

        @wraps(func)
        def decorated_func(*args, **kwargs):
            data = func(*args, **kwargs)
            if data is None:
                raise ObjectDoesNotExist()
            return data

        return decorated_func

    def post_list(self, data, trace_field="user_id"):
        data = dict(data)
        data[trace_field] = self.get_user_id()
        item = self.model(data)
        if self.foreign_data is not None:
            for fk in self.foreign_data:
                owner = self.foreign_data[fk].query.get(getattr(item, fk))
                if owner is None:
                    raise ObjectDoesNotExist()
                if not self.check_permissions(owner.user_id):
                    raise NoPermission()
        item.save()
        return item, 201

    def put_detail(self, data, *args, model=None):
        if model is None:
            model = self.query
        item = model(*args)
        if item is None:
            raise ObjectDoesNotExist()

        data = dict(data)
        data["user_id"] = self.get_user_id()
        item.update(data)

        return {"message": "Updated correctly"}, 200

    def patch_detail(self, data, *args, model=None):
        if model is None:
            model = self.query
        item = model(*args)

        if item is None:
            raise ObjectDoesNotExist()

        data = dict(data)
        data["user_id"] = self.get_user_id()
        item.patch(data)

        return {"message": "Patched correctly"}, 200

    def delete_detail(self, *args):

        item = self.query(*args)

        if item is None:
            raise ObjectDoesNotExist()

        if self.dependents is not None:
            for element in getattr(item, self.dependents):
                element.disable()
        if item:
            item.disable()

        return {"message": "The object has been deleted"}, 200

    def check_permissions(self, user):
        if self.get_user().id != user:
            return False
        else:
            return True

    def activate_item(self, **kwargs):
        item = self.query(**kwargs)
        item.activate()
        return item, 200
