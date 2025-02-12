"""
External endpoints to manage the cases: create new cases from raw data, from an existing instance or execution
or from an existing case, update the case info, patch its data, get all of them or one, move them and delete them.
These endpoints have different access url, but manage the same data entities
"""

# Import from libraries
from cornflow_client.airflow.api import get_schema, validate_and_continue
from flask import current_app
from flask_apispec import marshal_with, use_kwargs, doc
from flask_apispec.views import MethodResource
from flask_inflate import inflate
import jsonpatch
import logging as log


# Import from internal modules
from .meta_resource import MetaResource
from ..models import CaseModel, ExecutionModel, InstanceModel
from ..schemas.case import (
    CaseBase,
    CaseFromInstanceExecution,
    CaseRawRequest,
    CaseListResponse,
    CaseToInstanceResponse,
    CaseEditRequest,
    QueryFiltersCase,
    QueryCaseCompare,
    CaseCompareResponse,
)

from ..schemas.model_json import DataSchema
from ..shared.authentication import Auth
from ..shared.compress import compressed
from ..shared.exceptions import InvalidData, ObjectDoesNotExist


class CaseEndpoint(MetaResource, MethodResource):
    """
    Endpoint used to create a new case or get all the cases and their related information
    """

    @doc(description="Get all cases", tags=["Cases"])
    @Auth.auth_required
    @marshal_with(CaseListResponse(many=True))
    @use_kwargs(QueryFiltersCase, location="query")
    def get(self, **kwargs):
        """
        API (GET) method to get all directory structure of cases for the user
        It requires authentication to be passed in the form of a token that has to be linked to
        an existing session (login) made by a user

        :return: a dictionary with a tree structure of the cases and an integer with the HTTP status code
        :rtype: Tuple(dict, integer)
        """
        response = CaseModel.get_all_objects(self.get_user(), **kwargs)
        log.debug("User {} gets all cases".format(self.get_user_id()))
        return response

    @doc(description="Create a new case from raw data", tags=["Cases"])
    @Auth.auth_required
    @inflate
    @marshal_with(CaseListResponse)
    @use_kwargs(CaseRawRequest, location="json")
    def post(self, **kwargs):
        """ """
        data = dict(kwargs)
        data["user_id"] = self.get_user_id()
        item = CaseModel.from_parent_id(self.get_user(), data)
        item.save()
        log.info("User {} creates case {}".format(self.get_user_id(), item.id))
        return item, 201


class CaseFromInstanceExecutionEndpoint(MetaResource, MethodResource):
    """
    Endpoint used to create a new case from an already existing instance and execution
    """

    @doc(description="Create a new case from instance and execution", tags=["Cases"])
    @Auth.auth_required
    @marshal_with(CaseListResponse)
    @use_kwargs(CaseFromInstanceExecution, location="json")
    def post(self, **kwargs):
        """
        API method to create a new case from an existing instance or execution
        """
        instance_id = kwargs.get("instance_id", None)
        execution_id = kwargs.get("execution_id", None)

        data = {name: kwargs.get(name) for name in ["name", "description", "parent_id"]}

        if (instance_id is not None and execution_id is not None) or (
            instance_id is None and execution_id is None
        ):
            raise InvalidData(
                error="You must provide an instance_id OR an execution_id",
                status_code=400,
            )
        user = self.get_user()

        def get_instance_data(instance_id):
            instance = InstanceModel.get_one_object_from_user(user, instance_id)
            if instance is None:
                raise ObjectDoesNotExist("Instance does not exist")
            return dict(data=instance.data, schema=instance.schema)

        def get_execution_data(execution_id):
            execution = ExecutionModel.get_one_object_from_user(user, execution_id)
            if execution is None:
                raise ObjectDoesNotExist("Execution does not exist")
            data = get_instance_data(execution.instance_id)
            data["solution"] = execution.data
            return data

        if instance_id is not None:
            data = {**data, **get_instance_data(instance_id)}
        elif execution_id is not None:
            data = {**data, **get_execution_data(execution_id)}

        data = dict(data)
        data["user_id"] = self.get_user_id()
        item = CaseModel.from_parent_id(user, data)
        item.save()
        log.info(
            "User {} creates case {} from instance/execution".format(
                self.get_user_id(), item.id
            )
        )
        return item, 201


class CaseCopyEndpoint(MetaResource, MethodResource):
    """
    Copies the case to a new case. Original case id goes in the url
    """

    def __init__(self):
        super().__init__()
        self.model = CaseModel
        self.query = self.model.get_all_objects
        self.primary_key = "id"
        self.fields_to_copy = [
            "name",
            "description",
            "data",
            "schema",
            "solution",
            "path",
        ]
        self.fields_to_modify = ["name"]

    @doc(description="Copies a case to a new one", tags=["Cases"])
    @Auth.auth_required
    @marshal_with(CaseListResponse)
    def post(self, idx):
        """ """
        case = self.model.get_one_object_from_user(self.get_user(), idx)
        data = case.__dict__
        payload = dict()
        for key in data.keys():
            if key in self.fields_to_copy:
                payload[key] = data[key]
            if key in self.fields_to_modify:
                payload[key] = "Copy_" + payload[key]

        response = self.post_list(payload)
        log.info(
            "User {} copied case {} into {}".format(
                self.get_user_id(), idx, response[0].id
            )
        )
        return response


class CaseDetailsEndpoint(MetaResource, MethodResource):
    """
    Endpoint used to get the information of a single case, edit it or delete it
    """

    @doc(description="Get one case", tags=["Cases"], inherit=False)
    @Auth.auth_required
    @marshal_with(CaseListResponse)
    @MetaResource.get_data_or_404
    def get(self, idx):
        """
        API method to get an case created by the user and its related info.

        :param str idx: ID of the case
        :return: A dictionary with a message and an integer with the HTTP status code.
        :rtype: Tuple(dict, integer)
        """
        response = CaseModel.get_one_object_from_user(self.get_user(), idx)
        log.debug("User {} gets case {}".format(self.get_user_id(), idx))
        return response

    @doc(description="Edit a case", tags=["Cases"])
    @Auth.auth_required
    @use_kwargs(CaseEditRequest, location="json")
    def put(self, idx, **kwargs):
        """
        API method to edit a case created by the user and its basic related info (name, description and schema).

        :param int idx: ID of the case
        :return: A dictionary with a confirmation message and an integer with the HTTP status code.
        :rtype: Tuple(dict, integer)
        """
        log.info("User {} edits case {}".format(self.get_user_id(), idx))
        return self.put_detail(
            kwargs, self.get_user(), idx, model=CaseModel.get_one_object_from_user
        )

    @doc(description="Delete a case", tags=["Cases"])
    @Auth.auth_required
    def delete(self, idx):
        """
        API method to delete an existing case.
        It requires authentication to be passed in the form of a token that has to be linked to
        an existing session (login) made by a user.

        :param int idx: ID of the case
        :return: A dictionary with a confirmation message and an integer with the HTTP status code.
        :rtype: Tuple(dict, integer)
        """
        item = CaseModel.get_one_object_from_user(self.get_user(), idx)
        if item is None:
            raise ObjectDoesNotExist()
        CaseModel.delete(item)
        log.info("User {} deletes case {}".format(self.get_user_id(), idx))
        return {"message": "The object has been deleted"}, 200


class CaseDataEndpoint(CaseDetailsEndpoint):
    """
    Endpoint used to get the data of a given case
    """

    @doc(description="Get data of a case", tags=["Cases"], inherit=False)
    @Auth.auth_required
    @marshal_with(CaseBase)
    @MetaResource.get_data_or_404
    @compressed
    def get(self, idx):
        """
        API method to get data for a case by the user and its related info.
        It requires authentication to be passed in the form of a token that has to be linked to
        an existing session (login) made by a user.

        :param int idx: ID of the case
        :return: A dictionary with a message (error if authentication failed, or the execution does not exist or
          the data of the instance) and an integer with the HTTP status code.
        :rtype: Tuple(dict, integer)
        """
        response = CaseModel.get_one_object_from_user(self.get_user(), idx)
        log.debug("User {} retrieved data for case {}".format(self.get_user_id(), idx))
        return response

    @doc(description="Patches the data of a given case", tags=["Cases"], inherit=False)
    @Auth.auth_required
    @inflate
    @use_kwargs(CaseCompareResponse, location="json")
    def patch(self, idx, **kwargs):
        response = self.patch_detail(
            kwargs, self.get_user(), idx, model=CaseModel.get_one_object_from_user
        )
        log.info("User {} patches case {}".format(self.get_user_id(), idx))
        return response


class CaseToInstance(MetaResource, MethodResource):
    """
    Endpoint used to create a new instance or instance and execution from a stored case
    """

    def __init__(self):
        super().__init__()
        self.model = InstanceModel
        self.query = InstanceModel.get_all_objects
        self.primary_key = "id"

    @doc(
        description="Copies the information stored in a case into a new instance or instance and execution",
        tags=["Cases"],
    )
    @Auth.auth_required
    @marshal_with(CaseToInstanceResponse)
    def post(self, idx):
        """
        API method to copy the information stored in a case to a new instance or a new instance and execution.
        It requires authentication to be passed in the form of a token that has to be linked to
        an existing session (login) made by a user

        :param int idx: ID of the case that has to be copied to an instance or instance and execution
        :return: an object with the instance or instance and execution ID that have been created and the status code
        :rtype: Tuple (dict, integer)
        """
        case = CaseModel.get_one_object_from_user(self.get_user(), idx)

        if case is None:
            raise ObjectDoesNotExist()

        schema = case.schema
        payload = {
            "name": "instance_from_" + case.name,
            "description": "Instance created from " + case.description,
            "data": case.data,
            "schema": case.schema,
        }

        if schema is None:
            return self.post_list(payload)

        if schema == "pulp" or schema == "solve_model_dag":
            validate_and_continue(DataSchema(), payload["data"])
            return self.post_list(payload)

        config = current_app.config
        marshmallow_obj = get_schema(config, schema)
        validate_and_continue(marshmallow_obj(), payload["data"])
        response = self.post_list(payload)
        log.info(
            "User {} creates case {} from instance {}".format(
                self.get_user_id(), response[0].id, idx
            )
        )
        return response


class CaseCompare(MetaResource, MethodResource):
    """
    Endpoint used to generate the json patch of two given cases
    """

    def __init__(self):
        super().__init__()
        self.model = CaseModel
        self.query = CaseModel.get_all_objects
        self.primary_key = "id"

    @doc(
        description="Compares the data and / or solution of two given cases",
        tags=["Cases"],
    )
    @Auth.auth_required
    @marshal_with(CaseCompareResponse)
    @use_kwargs(QueryCaseCompare, location="query")
    @compressed
    def get(self, idx1, idx2, **kwargs):
        """
        API method to generate the json patch of two cases given by the user
        It requires authentication to be passed in the form of a token that has to be linked to
        an existing session (login) made by a user

        :param int idx1: ID of the base case for the comparison
        :param int idx2: ID of the case that has to be compared
        :return:an object with the instance or instance and execution ID that have been created and the status code
        :rtype: Tuple (dict, integer)
        """
        if idx1 == idx2:
            raise InvalidData("The case identifiers should be different", 400)
        case_1 = self.model.get_one_object_from_user(self.get_user(), idx1)
        case_2 = self.model.get_one_object_from_user(self.get_user(), idx2)

        if case_1 is None:
            raise ObjectDoesNotExist(
                "You don't have access to the first case or it doesn't exist"
            )
        elif case_2 is None:
            raise ObjectDoesNotExist(
                "You don't have access to the second case or it doesn't exist"
            )
        elif case_1.schema != case_2.schema:
            raise InvalidData("The cases asked to compare do not share the same schema")

        data = kwargs.get("data", True)
        solution = kwargs.get("solution", True)
        payload = dict()

        if data:
            payload["data_patch"] = jsonpatch.make_patch(case_1.data, case_2.data).patch
        if solution:
            payload["solution_patch"] = jsonpatch.make_patch(
                case_1.solution, case_2.solution
            ).patch
        log.debug(
            "User {} compared cases {} and {}".format(self.get_user_id(), idx1, idx2)
        )
        return payload, 200
