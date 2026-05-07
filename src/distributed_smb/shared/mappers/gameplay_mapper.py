from distributed_smb.domain.events import (
    BlockDestroyedEvent,
    GateStateChangedEvent,
    PowerUpCollectedEvent,
)
from distributed_smb.shared.messages.gameplay import (
    BlockDestroyedMessage,
    GateStateChangedMessage,
    PowerUpCollectedMessage,
)


def event_to_message(event):
    if isinstance(event, BlockDestroyedEvent):
        return BlockDestroyedMessage(position=event.position)
    if isinstance(event, PowerUpCollectedEvent):
        return PowerUpCollectedMessage(powerup_id=event.powerup_id, player_id=event.player_id)
    if isinstance(event, GateStateChangedEvent):
        return GateStateChangedMessage(gate_id=event.gate_id, new_state=event.new_state)
