import spectroscope

from ethereumapis.v1alpha1 import beacon_chain_pb2, beacon_chain_pb2_grpc
from spectroscope.model import ChainTimestamp, ValidatorIdentity
from spectroscope.model.update import (
    ValidatorBalanceUpdate,
    ValidatorStatusUpdate,
    UpdateBatch,
)
from spectroscope.module import Module, Plugin, Subscriber
from typing import List, Set, Tuple, Type


log = spectroscope.log()


class BeaconChainStreamer:
    """Stream ValidatorInfo messages from the beacon chain gRPC endpoint.

    Args:
        stub: gRPC stub interface to the beacon chain. Useful for dependency injection.
        modules: Modules and arguments to initialize before streaming messages.
    """

    def __init__(
        self,
        stub: beacon_chain_pb2_grpc.BeaconChainStub,
        modules: List[Tuple[Type[Module], dict]],
    ):
        self.stub = stub
        self.validator_set: Set[bytes] = set()

        self.subscribers = list()
        self.plugins = list()
        for module, config in modules:
            if issubclass(module, Subscriber):
                self.subscribers.append(module.register(**config))
            elif issubclass(module, Plugin):
                self.plugins.append(module.register(**config))
            else:
                raise TypeError

    def count_validators(self):
        return len(self.validator_set)

    def add_validators(self, validators: Set[bytes]):
        for validator in validators:
            if validator not in self.validator_set:
                self.validator_set.add(validator)

    def remove_validators(self, validators: Set[bytes]):
        for validator in validators:
            try:
                self.validator_set.remove(validator)
            except KeyError as unknown_key:
                log.warn("Warning! Failed to delete a key !")
                log.warn("the key {} not found in beacon stream".format(unknown_key))

    def update_validators(self, validators: Set[bytes]):
        self.validator_set = validators

    def _generate_messages(self):
        log.info("Watching for {} validators".format(len(self.validator_set)))
        yield beacon_chain_pb2.ValidatorChangeSet(
            action=beacon_chain_pb2.SET_VALIDATOR_KEYS,
            public_keys=self.validator_set,
        )

    def stream_responses(self, validator_info):
        log.debug("Received update for validator idx {}".format(validator_info.index))
        updates = [
            ValidatorStatusUpdate(status=validator_info.status),
            ValidatorBalanceUpdate(
                balance=validator_info.balance,
                effectiveBalance=validator_info.effective_balance,
            ),
        ]

        responses = list()
        for subscriber in self.subscribers:
            batch = UpdateBatch(
                validator=ValidatorIdentity(
                    pubkey=validator_info.public_key, idx=validator_info.index
                ),
                timestamp=ChainTimestamp(epoch=validator_info.epoch, slot=0),
                updates=list(
                    filter(lambda x: type(x) in subscriber.consumed_types, updates)
                ),
            )
            if batch.updates:
                responses.extend(subscriber.consume(batch))

        for plugin in self.plugins:
            actions = list(
                filter(lambda x: type(x) in plugin.consumed_types, responses)
            )
            if actions:
                plugin.consume(actions)

    async def stream(self):
        async for stream_value in self.stub.StreamValidatorsInfo(
            self._generate_messages()
        ).__aiter__():
            self.stream_responses(stream_value)
