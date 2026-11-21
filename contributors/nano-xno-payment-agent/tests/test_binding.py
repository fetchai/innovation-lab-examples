"""Order binding, single-use claims and bounded RPC (no network, no uagents needed)."""

import io
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nano_binding as nb  # noqa: E402
import verify_nano  # noqa: E402

PAY_TO = "nano_1111111111111111111111111111111111111111111111111111hifc8npp"
PRICE = 10**26
NOW = 1_000_000


class Store(dict):
    def set(self, k, v):
        self[k] = v

    def has(self, k):
        return k in self

    def remove(self, k):
        self.pop(k, None)


def test_commitment_matches_standard_vector():
    rep = nb.commitment_rep_account("order-0001", PAY_TO, 50000000000000000000000000000)
    # Vector from docs/BINDING-STANDARD.md (xno-call-binding), "Option C commitment_rep_account".
    assert rep == "nano_33q9dassq66es6mcay83n5kypqgpzjikr9bkc9ope9xch1borfphgehj4ozj"


def test_account_encoding_matches_the_network():
    # Genesis account and its public key, as every Nano node and wallet show them.
    genesis_pub = bytes.fromhex(
        "E89208DD038FBB269987689621D52292AE9C35941A7484756ECCED92A65093BA"
    )
    assert (
        nb.pubkey_to_account(genesis_pub)
        == "nano_3t6k35gi95xu6tergt6p69ck76ogmitsa8mnijtpxm9fkcm736xtoncuohr3"
    )
    assert nb.pubkey_to_account(bytes(32)) == PAY_TO
    # 256 bits in 52 characters leave 4 zero bits on top: always 1 or 3.
    for i in range(64):
        rep = nb.commitment_rep_account(f"order-{i}", PAY_TO, PRICE)
        assert rep[5] in "13" and len(rep) == 65


def test_verify_accepts_the_representative_as_a_node_prints_it():
    # block_info returns the representative in the network's own encoding; the
    # order commitment must compare equal to that string, not only to itself.
    node_rep = "nano_33q9dassq66es6mcay83n5kypqgpzjikr9bkc9ope9xch1borfphgehj4ozj"
    rep = nb.commitment_rep_account("order-0001", PAY_TO, 50000000000000000000000000000)
    assert _verify(_block(node_rep), expected_representative=rep)


def test_order_ids_are_opaque_and_commitments_differ():
    s = Store()
    a = nb.new_order(s, "buyer", PAY_TO, PRICE, 300, NOW)
    b = nb.new_order(s, "buyer", PAY_TO, PRICE, 300, NOW)
    assert a[0] != b[0] and len(a[0]) == 32 and a[1] != b[1]


def test_block_is_one_to_one_with_order():
    s = Store()
    o1 = nb.new_order(s, "buyer", PAY_TO, PRICE, 300, NOW)[0]
    o2 = nb.new_order(s, "buyer", PAY_TO, PRICE, 300, NOW)[0]
    assert nb.claim_block(s, o1, "buyer", "H1", NOW)[1] is None
    assert nb.claim_block(s, o2, "buyer", "H1", NOW)[1] == "block already claimed"
    assert (
        nb.claim_block(s, o1, "buyer", "H2", NOW)[1] == "order already claimed or paid"
    )
    nb.finalize(s, o1)
    assert (
        nb.claim_block(s, o1, "buyer", "H3", NOW)[1] == "order already claimed or paid"
    )


def test_claim_refuses_other_requester_unknown_and_expired():
    s = Store()
    o = nb.new_order(s, "buyer", PAY_TO, PRICE, 300, NOW)[0]
    assert (
        nb.claim_block(s, o, "mallory", "H1", NOW)[1]
        == "order belongs to another requester"
    )
    assert nb.claim_block(s, "nope", "buyer", "H1", NOW)[1] == "unknown order"
    assert nb.claim_block(s, o, "buyer", "H1", NOW + 301)[1] == "order expired"


def test_release_reopens_order_and_survives_restart():
    s = Store()
    o = nb.new_order(s, "buyer", PAY_TO, PRICE, 300, NOW)[0]
    nb.claim_block(s, o, "buyer", "H1", NOW)
    assert nb.claim_block(s, o, "buyer", "H1", NOW)[0] is None
    nb.release_block(s, o, "H1")
    assert nb.claim_block(s, o, "buyer", "H1", NOW)[1] is None
    nb.finalize(s, o)
    restarted = Store(s)  # everything lives in the store, nothing in process memory
    assert (
        nb.claim_block(restarted, o, "buyer", "H9", NOW)[1]
        == "order already claimed or paid"
    )


def _block(rep, ts="1000100"):
    return {
        "subtype": "send",
        "confirmed": "true",
        "amount": str(PRICE),
        "local_timestamp": ts,
        "contents": {"link_as_account": PAY_TO, "representative": rep},
    }


def _verify(block, **kw):
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=block):
        return verify_nano.verify_nano_send("H", PAY_TO, "0.0001", **kw)


def test_verify_requires_the_order_commitment_in_representative():
    s = Store()
    o, rep, exp = nb.new_order(s, "buyer", PAY_TO, PRICE, 300, NOW)
    other = nb.commitment_rep_account("another-order", PAY_TO, PRICE)
    assert _verify(_block(rep), expected_representative=rep)
    assert not _verify(_block(other), expected_representative=rep)
    assert not _verify(_block(PAY_TO), expected_representative=rep)


def test_verify_window_uses_block_time():
    assert _verify(_block("r"), valid_until=1000200)
    assert not _verify(_block("r", ts="1000300"), valid_until=1000200)
    assert not _verify(_block("r", ts=""), valid_until=1000200)


def test_rpc_refuses_plain_http_non_loopback_and_oversize():
    assert verify_nano.rpc_url_allowed("https://rpc.nano.to")
    assert verify_nano.rpc_url_allowed("http://127.0.0.1:7076")
    assert not verify_nano.rpc_url_allowed("http://rpc.example.com")
    assert not verify_nano.rpc_url_allowed("ftp://x")
    with mock.patch.object(verify_nano, "NANO_RPC_URL", "http://rpc.example.com"):
        try:
            verify_nano.nano_rpc_post("block_info", {})
        except ValueError:
            pass
        else:
            raise AssertionError("plain http accepted")

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    big = Resp(b"{" + b" " * (verify_nano.RPC_MAX_BYTES + 10) + b"}")
    with mock.patch("urllib.request.urlopen", return_value=big):
        try:
            verify_nano.nano_rpc_post("block_info", {})
        except ValueError:
            pass
        else:
            raise AssertionError("oversize accepted")
