"""Model for the instances"""

# Import from libraries
import hashlib

# Imported from internal models
from .meta_model import BaseDataModel
from ..shared.utils import db


class InstanceModel(BaseDataModel):
    """
    Model class for the Instances
    It inherits from :class:`BaseDataModel` to have the trace fields and user field

    The :class:`InstanceModel` has the following fields:

    - **id**: int, the primary key for the executions, a hash generated upon creation of the instance
      and the id given back to the user.The hash is generated from the creation time and the user id.
    - **data**: dict (JSON), the data structure of the instance (:class:`DataSchema`)
    - **name**: str, the name given to the instance by the user.
    - **description**: str, the description given to the instance by the user. It is optional.
    - **executions**: relationship, not a field in the model but the relationship between the _class:`InstanceModel`
      and its dependent :class:`ExecutionModel`.
    - **user_id**: int, the foreign key for the user (:class:`UserModel`). It links the execution to its owner.
    - **created_at**: datetime, the datetime when the execution was created (in UTC).
      This datetime is generated automatically, the user does not need to provide it.
    - **updated_at**: datetime, the datetime when the execution was last updated (in UTC).
      This datetime is generated automatically, the user does not need to provide it.
    - **deleted_at**: datetime, the datetime when the execution was deleted (in UTC). Even though it is deleted,
      actually, it is not deleted from the database, in order to have a command that cleans up deleted data
      after a certain time of its deletion.
      This datetime is generated automatically, the user does not need to provide it.
    - **data_hash**: a hash of the data json using SHA256
    """

    # Table name in the database
    __tablename__ = "instances"

    # Model fields
    id = db.Column(db.String(256), nullable=False, primary_key=True)
    executions = db.relationship(
        "ExecutionModel",
        backref="instances",
        lazy=True,
        primaryjoin="and_(InstanceModel.id==ExecutionModel.instance_id, "
        "ExecutionModel.deleted_at==None)",
    )

    def __init__(self, data):
        """
        :param dict data: the parsed json got from an endpoint that contains all the required
            information to create a new instance
        """
        super().__init__(data)
        self.id = hashlib.sha1(
            (str(self.created_at) + " " + str(self.user_id)).encode()
        ).hexdigest()

    def __repr__(self):
        """
        Method to represent the class :class:`InstanceModel`

        :return: The representation of the :class:`InstanceModel`
        :rtype: str
        """
        return "<id {}>".format(self.id)

    def __str__(self):
        """
        Method to print a string representation of the :class:`InstanceModel`

        :return: The string for the :class:`InstanceModel`
        :rtype: str
        """
        return "<id {}>".format(self.id)
