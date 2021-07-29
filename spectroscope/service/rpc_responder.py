from ethereumapis.v1alpha1.validator_pb2 import UNKNOWN_STATUS
import spectroscope
from spectroscope.model.update import DatabaseBatch, DatabaseUpdate
from spectroscope.module import Module, Plugin, Subscriber
from spectroscope.constants import enums
from typing import List, Set, Tuple, Type
from proto_files.validator import service_pb2, node_pb2, service_pb2_grpc

# This servicer will take the module necessary to work:
# The database plugin used: For now we are using mongodb
# The db_update subscriber that listens to DatabaseBatch Updates.

log = spectroscope.log()


class RPCValidatorServicer(service_pb2_grpc.ValidatorServiceServicer):
    def __init__(
        self,
        modules: List[Tuple[Type[Module], dict]],
    ):
        self.subscribers = list()
        self.plugins = list()
        for module, config in modules:
            if issubclass(module, Subscriber):
                self.subscribers.append(module.register(**config))
            elif issubclass(module, Plugin):
                self.plugins.append(module.register(**config))
            else:
                raise TypeError

    def AddNodes(self, request, context):
        updates = [
            DatabaseUpdate(
                update_type=enums.RequestTypes.ADD.value,
                status=enums.ValidatorStatus.DEPOSITED.value,
                validator_keys=[
                    val.validator_key for val in request.validators.validator
                ],
            )
        ]
        return self._return_api(self._send_requests(updates))

    def UpNodes(self, request, context):
        updates = [
            DatabaseUpdate(
                update_type=enums.RequestTypes.UP.value,
                status=request.status,
                validator_keys=[
                    val.validator_key for val in request.validators.validator
                ],
            )
        ]
        return self._return_api(self._send_requests(updates))

    def DelNodes(self, request, context):
        updates = [
            DatabaseUpdate(
                update_type=enums.RequestTypes.DEL.value,
                status=enums.ValidatorStatus.ACTIVE.value,
                validator_keys=[
                    val.validator_key for val in request.validators.validator
                ],
            )
        ]
        return self._return_api(self._send_requests(updates))

    def GetNodes(self, request, context):
        updates = [
            DatabaseUpdate(
                status=enums.ValidatorStatus.UNKNOWN_STATUS.value,
                update_type=enums.RequestTypes.GET.value,
                validator_keys=[
                    val.validator_key for val in request.validators.validator
                ],
            )
        ]
        return self._return_get(self._send_requests(updates))

    def _send_requests(self, updates):
        responses = list()
        for subscriber in self.subscribers:
            batch = DatabaseBatch(
                updates=list(
                    filter(lambda x: type(x) in subscriber.consumed_types, updates)
                ),
            )
            if batch.updates:
                responses.extend(subscriber.consume(batch))

        api_results = []
        for plugin in self.plugins:
            actions = list(
                filter(lambda x: type(x) in plugin.consumed_types, responses)
            )
            if actions:
                api_results = plugin.consume(actions)
        return api_results

    # def _return_api(self, result_api):
    #     response = service_pb2.RequestsResult()
    #     for result in result_api:
    #         if result['modified_count']> 0:
    #             pass
    #             #do something in particular, not implemented yet
    #         elif result['inserted_count']:

    def _return_api(self, result_api):
        response = service_pb2.RequestsResult()
        modified_val = 0
        try:
            modified_val = [modified_val + x for x in result_api][0]
            if modified_val:
                response.status = 201
            else:
                response.status = 200
        finally:
            response.count = modified_val
            return response

    def _return_get(self, result_api):
        response = service_pb2.ValidatorList()
        validator_list = [
            node_pb2.Validator(validator_key=val.encode())
            for result in result_api
            for val in result
        ]
        for val in validator_list:
            response.validator.append(val)
        return response

    def get_validators(self):
        request = service_pb2.GetNodesRequest(validators=[])
        return self.GetNodes(request, None)
