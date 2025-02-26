from __future__ import annotations

from typing import List, Optional

import pytest

from chia.consensus.block_record import BlockRecord
from chia.consensus.blockchain import Blockchain, StateChangeSummary
from chia.consensus.cost_calculator import NPCResult
from chia.full_node.hint_management import get_hints_and_subscription_coin_ids
from chia.simulator.block_tools import BlockTools
from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.spend_bundle_conditions import Spend, SpendBundleConditions
from chia.util.hash import std_hash
from chia.util.ints import uint32, uint64
from tests.blockchain.blockchain_test_utils import _validate_and_add_block

coin_ids = [std_hash(i.to_bytes(4, "big")) for i in range(10)]
phs = [std_hash(i.to_bytes(4, "big")) for i in range(10)]
spends: List[Spend] = [
    Spend(
        coin_ids[0],
        phs[0],
        None,
        uint64(5),
        [
            (phs[2], uint64(123), b""),
            (phs[4], uint64(3), b"1" * 32),
        ],
        [],
    ),
    Spend(
        coin_ids[2],
        phs[0],
        None,
        uint64(6),
        [
            (phs[7], uint64(123), b""),
            (phs[4], uint64(6), b""),
            (phs[9], uint64(123), b"1" * 32),
        ],
        [],
    ),
    Spend(
        coin_ids[1],
        phs[7],
        None,
        uint64(2),
        [
            (phs[5], uint64(123), b""),
            (phs[6], uint64(5), b"1" * 3),
        ],
        [],
    ),
]


@pytest.mark.asyncio
async def test_hints_to_add(bt: BlockTools, empty_blockchain: Blockchain) -> None:
    blocks = bt.get_consecutive_blocks(2)
    await _validate_and_add_block(empty_blockchain, blocks[0])
    await _validate_and_add_block(empty_blockchain, blocks[1])
    br: Optional[BlockRecord] = empty_blockchain.get_peak()
    assert br is not None
    sbc: SpendBundleConditions = SpendBundleConditions(spends, uint64(0), uint32(0), uint64(0), [], uint64(0))
    npc_res = [NPCResult(None, None, uint64(0)), NPCResult(None, sbc, uint64(0))]

    scs = StateChangeSummary(br, uint32(0), [], npc_res, [])
    hints_to_add, lookup_coin_ids = get_hints_and_subscription_coin_ids(scs, {}, {})
    assert len(lookup_coin_ids) == 0

    first_coin_id: bytes32 = Coin(bytes32(spends[0].coin_id), bytes32(phs[4]), uint64(3)).name()
    second_coin_id: bytes32 = Coin(bytes32(spends[2].coin_id), bytes32(phs[6]), uint64(5)).name()
    third_coin_id: bytes32 = Coin(bytes32(spends[1].coin_id), bytes32(phs[9]), uint64(123)).name()
    assert set(hints_to_add) == {(first_coin_id, b"1" * 32), (second_coin_id, b"1" * 3), (third_coin_id, b"1" * 32)}


@pytest.mark.asyncio
async def test_lookup_coin_ids(bt: BlockTools, empty_blockchain: Blockchain) -> None:
    blocks = bt.get_consecutive_blocks(2)
    await _validate_and_add_block(empty_blockchain, blocks[0])
    await _validate_and_add_block(empty_blockchain, blocks[1])
    br: Optional[BlockRecord] = empty_blockchain.get_peak()
    assert br is not None
    sbc: SpendBundleConditions = SpendBundleConditions(spends, uint64(0), uint32(0), uint64(0), [], uint64(0))
    npc_res = [NPCResult(None, None, uint64(0)), NPCResult(None, sbc, uint64(0))]

    rewards: List[Coin] = [
        Coin(coin_ids[8], phs[8], uint64(1)),
        Coin(coin_ids[9], phs[9], uint64(2)),
        Coin(coin_ids[5], phs[8], uint64(1234)),
    ]
    scs = StateChangeSummary(br, uint32(0), [], npc_res, rewards)

    # Removal ID and addition PH
    coin_subscriptions = {coin_ids[1]: {bytes32(b"2" * 32)}}
    ph_subscriptions = {phs[4]: {bytes32(b"3" * 32)}}

    _, lookup_coin_ids = get_hints_and_subscription_coin_ids(scs, coin_subscriptions, ph_subscriptions)

    first_coin_id: bytes32 = Coin(bytes32(spends[0].coin_id), bytes32(phs[4]), uint64(3)).name()
    second_coin_id: bytes32 = Coin(bytes32(spends[1].coin_id), bytes32(phs[4]), uint64(6)).name()
    assert set(lookup_coin_ids) == {coin_ids[1], first_coin_id, second_coin_id}

    # Removal PH and addition ID
    coin_subscriptions = {first_coin_id: {bytes32(b"5" * 32)}}
    ph_subscriptions = {phs[0]: {bytes32(b"6" * 32)}}
    _, lookup_coin_ids = get_hints_and_subscription_coin_ids(scs, coin_subscriptions, ph_subscriptions)
    assert set(lookup_coin_ids) == {first_coin_id, coin_ids[0], coin_ids[2]}

    # Subscribe to hint
    third_coin_id: bytes32 = Coin(bytes32(spends[1].coin_id), phs[9], uint64(123)).name()
    ph_subscriptions = {bytes32(b"1" * 32): {bytes32(b"7" * 32)}}
    _, lookup_coin_ids = get_hints_and_subscription_coin_ids(scs, {}, ph_subscriptions)
    assert set(lookup_coin_ids) == {first_coin_id, third_coin_id}

    # Reward PH
    ph_subscriptions = {rewards[0].puzzle_hash: {bytes32(b"8" * 32)}}
    _, lookup_coin_ids = get_hints_and_subscription_coin_ids(scs, {}, ph_subscriptions)
    assert set(lookup_coin_ids) == {rewards[0].name(), rewards[2].name()}

    # Reward coin id + reward ph
    coin_subscriptions = {rewards[1].name(): {bytes32(b"9" * 32)}}
    _, lookup_coin_ids = get_hints_and_subscription_coin_ids(scs, coin_subscriptions, ph_subscriptions)
    assert set(lookup_coin_ids) == {rewards[1].name(), rewards[0].name(), rewards[2].name()}
