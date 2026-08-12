"""Protected executable contracts for Phase 4A wallet lifecycle and addresses.

These contracts are defined before production implementation. They remain
expected failures only while the complete Phase 4A public surface is absent.
Once that surface exists, every contract activates automatically.

Implementers may add complementary tests, but must not weaken, skip, delete,
replace, or rewrite this file to obtain a passing build.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import bitheim.domain.errors as errors_module
from bitheim.infrastructure.compose.adapter import ComposeLifecycleAdapter
from bitheim.interfaces.cli import build_parser, main


def _optional_module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


def _required_attr(module: Any, name: str) -> Any:
    """Resolve a contract surface that is intentionally absent before implementation."""
    return getattr(module, name)


wallet_domain = _optional_module("bitheim.domain.wallet")
wallet_ports = _optional_module("bitheim.application.wallet_ports")
wallet_service_module = _optional_module("bitheim.application.wallet_service")
wallet_rpc_module = _optional_module("bitheim.infrastructure.bitcoin.wallet_rpc")

WalletLifecycleResult: Any = getattr(wallet_domain, "WalletLifecycleResult", None)
WalletAddress: Any = getattr(wallet_domain, "WalletAddress", None)
WalletManagementPort: Any = getattr(wallet_ports, "WalletManagementPort", None)
WalletService: Any = getattr(wallet_service_module, "WalletService", None)
BitcoinWalletRpcClient: Any = getattr(wallet_rpc_module, "BitcoinWalletRpcClient", None)

_CAPABILITY_AVAILABLE = all(
    (
        WalletLifecycleResult is not None,
        WalletAddress is not None,
        WalletManagementPort is not None,
        WalletService is not None,
        BitcoinWalletRpcClient is not None,
        callable(getattr(WalletService, "create_wallet", None)),
        callable(getattr(WalletService, "load_wallet", None)),
        callable(getattr(WalletService, "get_new_address", None)),
        callable(getattr(BitcoinWalletRpcClient, "create_wallet", None)),
        callable(getattr(BitcoinWalletRpcClient, "load_wallet", None)),
        callable(getattr(BitcoinWalletRpcClient, "get_new_address", None)),
        callable(getattr(ComposeLifecycleAdapter, "create_wallet", None)),
        callable(getattr(ComposeLifecycleAdapter, "load_wallet", None)),
        callable(getattr(ComposeLifecycleAdapter, "get_new_address", None)),
    )
)

pytestmark = pytest.mark.xfail(
    not _CAPABILITY_AVAILABLE,
    reason="Phase 4A wallet lifecycle and receiving-address surface is not implemented yet",
    strict=True,
)

WALLET_NAME = "lab-wallet"
ADDRESS = "bcrt1qcontractaddress000000000000000000000000000000000000"
PRIVATE_SENTINEL = "private-wallet-sentinel"
ADDRESS_SENTINEL = "bcrt1qprivateaddresssentinel"


class _WalletPortFake:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def create_wallet(self, wallet_name: str, timeout: float) -> Any:
        self.calls.append(("create", wallet_name, timeout))
        return WalletLifecycleResult(
            wallet_name=wallet_name,
            created=True,
            already_loaded=False,
        )

    def load_wallet(self, wallet_name: str, timeout: float) -> Any:
        self.calls.append(("load", wallet_name, timeout))
        return WalletLifecycleResult(
            wallet_name=wallet_name,
            created=False,
            already_loaded=False,
        )

    def get_new_address(self, wallet_name: str, timeout: float) -> Any:
        self.calls.append(("address", wallet_name, timeout))
        return WalletAddress(wallet_name=wallet_name, address=ADDRESS)


def _lifecycle(**overrides: object) -> Any:
    values: dict[str, object] = {
        "wallet_name": WALLET_NAME,
        "created": True,
        "already_loaded": False,
    }
    values.update(overrides)
    return WalletLifecycleResult(**values)


def _address(**overrides: object) -> Any:
    values: dict[str, object] = {"wallet_name": WALLET_NAME, "address": ADDRESS}
    values.update(overrides)
    return WalletAddress(**values)


def test_wallet_domain_models_are_frozen_slotted_and_deterministic() -> None:
    lifecycle = _lifecycle()
    address = _address()

    for value in (lifecycle, address):
        assert dataclasses.is_dataclass(type(value))
        assert vars(type(value))["__dataclass_params__"].frozen is True
        assert not hasattr(value, "__dict__")

    assert lifecycle.to_dict() == {
        "already_loaded": False,
        "created": True,
        "wallet_name": WALLET_NAME,
    }
    assert address.to_dict() == {"address": ADDRESS, "wallet_name": WALLET_NAME}


@pytest.mark.parametrize(
    "wallet_name",
    [
        "",
        "A-wallet",
        "1wallet",
        "wallet.name",
        "wallet/name",
        "wallet\\name",
        "wallet name",
        "wallet%2fname",
        "wallet\nname",
        "wállét",
        "w" * 65,
    ],
)
def test_wallet_domain_rejects_invalid_or_ambiguous_names(wallet_name: str) -> None:
    with pytest.raises(ValueError):
        _lifecycle(wallet_name=wallet_name)
    with pytest.raises(ValueError):
        _address(wallet_name=wallet_name)


@pytest.mark.parametrize("wallet_name", ["a", "lab-wallet", "wallet_01", "w" * 64])
def test_wallet_domain_accepts_the_exact_public_name_language(wallet_name: str) -> None:
    assert _lifecycle(wallet_name=wallet_name).wallet_name == wallet_name


@pytest.mark.parametrize(
    ("created", "already_loaded"),
    [(True, True), (1, False), (False, 0)],
)
def test_wallet_lifecycle_rejects_ambiguous_or_non_boolean_facts(
    created: object, already_loaded: object
) -> None:
    with pytest.raises(ValueError):
        _lifecycle(created=created, already_loaded=already_loaded)


@pytest.mark.parametrize("address", ["", "x" * 129, "bcrt1qline\nbreak", 1, None])
def test_wallet_address_rejects_empty_unbounded_or_non_text_results(address: object) -> None:
    with pytest.raises(ValueError):
        _address(address=address)


def test_wallet_port_is_structural_and_exposes_only_phase4a_capabilities() -> None:
    assert _required_attr(WalletManagementPort, "_is_protocol") is True
    assert callable(WalletManagementPort.create_wallet)
    assert callable(WalletManagementPort.load_wallet)
    assert callable(WalletManagementPort.get_new_address)
    assert not hasattr(WalletManagementPort, "send")
    assert not hasattr(WalletManagementPort, "export_private_key")
    assert not hasattr(WalletManagementPort, "dump_wallet")


@pytest.mark.parametrize("operation", ["create_wallet", "load_wallet", "get_new_address"])
def test_application_service_delegates_one_bounded_operation(operation: str) -> None:
    port = _WalletPortFake()
    service = WalletService(port)

    result = getattr(service, operation)(WALLET_NAME, timeout=4.5)

    expected_kind = {
        "create_wallet": "create",
        "load_wallet": "load",
        "get_new_address": "address",
    }[operation]
    assert port.calls == [(expected_kind, WALLET_NAME, 4.5)]
    assert result.wallet_name == WALLET_NAME


@pytest.mark.parametrize("timeout", [0, -1, 61, math.nan, math.inf, True, "10"])
def test_application_rejects_invalid_deadline_before_port_dispatch(timeout: object) -> None:
    port = _WalletPortFake()
    service = WalletService(port)

    with pytest.raises(errors_module.RpcError):
        service.create_wallet(WALLET_NAME, timeout=timeout)

    assert port.calls == []


def test_application_rejects_invalid_wallet_name_before_port_dispatch() -> None:
    port = _WalletPortFake()
    service = WalletService(port)

    with pytest.raises(ValueError):
        service.create_wallet(PRIVATE_SENTINEL + "/../wallet")

    assert port.calls == []


def test_rpc_create_uses_explicit_named_descriptor_wallet_intent() -> None:
    client = BitcoinWalletRpcClient()
    send = MagicMock(return_value={"name": WALLET_NAME, "warning": ""})
    with patch.object(client, "_send_request", send):
        result = client.create_wallet(WALLET_NAME, timeout=5.0)

    assert result == _lifecycle()
    assert send.call_count == 1
    assert send.call_args.args[0] == "createwallet"
    assert send.call_args.args[1] == {
        "wallet_name": WALLET_NAME,
        "disable_private_keys": False,
        "blank": False,
        "passphrase": "",
        "avoid_reuse": False,
        "descriptors": True,
        "load_on_startup": True,
        "external_signer": False,
    }
    assert send.call_args.kwargs.get("wallet_name") is None


def test_rpc_create_rejects_existing_wallet_as_typed_conflict_without_echo() -> None:
    conflict = _required_attr(errors_module, "WalletConflictError")
    client = BitcoinWalletRpcClient()
    with (
        patch.object(client, "_send_request", side_effect=conflict("Wallet already exists.")),
        pytest.raises(conflict) as caught,
    ):
        client.create_wallet(PRIVATE_SENTINEL)

    assert PRIVATE_SENTINEL not in str(caught.value)
    assert caught.value.__cause__ is None


def test_rpc_load_short_circuits_when_wallet_is_already_loaded() -> None:
    client = BitcoinWalletRpcClient()
    send = MagicMock(return_value=[WALLET_NAME])
    with patch.object(client, "_send_request", send):
        result = client.load_wallet(WALLET_NAME)

    assert result == _lifecycle(created=False, already_loaded=True)
    assert send.call_count == 1
    assert send.call_args.args[:2] == ("listwallets", [])


def test_rpc_load_uses_one_remaining_deadline_for_list_then_load() -> None:
    client = BitcoinWalletRpcClient()
    observed: list[tuple[str, object, float]] = []

    def send(method: str, params: object, *, timeout: float, **_kwargs: object) -> object:
        observed.append((method, params, timeout))
        return [] if method == "listwallets" else {"name": WALLET_NAME, "warning": ""}

    with patch.object(client, "_send_request", side_effect=send):
        result = client.load_wallet(WALLET_NAME, timeout=8.0)

    assert result == _lifecycle(created=False, already_loaded=False)
    assert [method for method, _params, _timeout in observed] == ["listwallets", "loadwallet"]
    assert observed[0][1] == []
    assert observed[1][1] == {"filename": WALLET_NAME}
    assert 0 < observed[1][2] <= observed[0][2] <= 8.0


def test_rpc_load_absent_wallet_maps_to_typed_not_found_without_raw_message() -> None:
    not_found = _required_attr(errors_module, "WalletNotFoundError")
    client = BitcoinWalletRpcClient()
    send = MagicMock(side_effect=[[], not_found("Raw private path /wallets/sentinel")])
    with (
        patch.object(client, "_send_request", send),
        pytest.raises(not_found) as caught,
    ):
        client.load_wallet(WALLET_NAME)

    assert "/wallets/sentinel" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_rpc_address_uses_explicit_wallet_context_and_bech32() -> None:
    client = BitcoinWalletRpcClient()
    send = MagicMock(return_value=ADDRESS)
    with patch.object(client, "_send_request", send):
        result = client.get_new_address(WALLET_NAME, timeout=3.0)

    assert result == _address()
    assert send.call_count == 1
    assert send.call_args.args[:2] == ("getnewaddress", ["", "bech32"])
    assert send.call_args.kwargs["wallet_name"] == WALLET_NAME


@pytest.mark.parametrize("result", [None, 1, "", "x" * 129, "bcrt1qbad\naddress"])
def test_rpc_address_rejects_malformed_results(result: object) -> None:
    malformed = errors_module.RpcMalformedResponseError
    client = BitcoinWalletRpcClient()
    with (
        patch.object(client, "_send_request", return_value=result),
        pytest.raises(malformed),
    ):
        client.get_new_address(WALLET_NAME)


def test_rpc_method_set_contains_phase4a_only_and_no_secret_exports() -> None:
    allowed = _required_attr(wallet_rpc_module, "ALLOWED_WALLET_RPC_METHODS")
    assert {"createwallet", "loadwallet", "listwallets", "getnewaddress"} <= allowed
    assert not (
        {
            "dumpprivkey",
            "dumpwallet",
            "listdescriptors",
            "importdescriptors",
            "sendtoaddress",
            "walletpassphrase",
            "unloadwallet",
        }
        & allowed
    )


def test_cli_parser_exposes_only_phase4a_wallet_commands() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "wallet" in help_text

    for command in ("create", "load", "address"):
        with pytest.raises(SystemExit) as caught:
            parser.parse_args(["wallet", command, "--help"])
        assert caught.value.code == 0

    with pytest.raises(SystemExit):
        parser.parse_args(["wallet", "send", "--help"])


@pytest.mark.parametrize("command", ["create", "load"])
def test_cli_lifecycle_json_is_deterministic_and_stdout_only(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _lifecycle(created=command == "create", already_loaded=False)
    method = f"{command}_wallet"
    with (
        patch.object(ComposeLifecycleAdapter, method, return_value=result),
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
    ):
        exit_code = main(["wallet", command, "--name", WALLET_NAME, "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out == json.dumps(result.to_dict(), separators=(",", ":")) + "\n"


def test_cli_address_json_contains_only_requested_wallet_and_address(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _address()
    with (
        patch.object(ComposeLifecycleAdapter, "get_new_address", return_value=result),
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
    ):
        exit_code = main(["wallet", "address", "--name", WALLET_NAME, "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == result.to_dict()


def test_cli_container_context_uses_application_service_without_recursive_delegation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch.dict("os.environ", {"BITHEIM_EXECUTION_CONTEXT": "container"}),
        patch.object(WalletService, "create_wallet", return_value=_lifecycle()) as create,
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.create_wallet"
        ) as compose_create,
    ):
        exit_code = main(["wallet", "create", "--name", WALLET_NAME, "--json"])

    assert exit_code == 0
    create.assert_called_once()
    compose_create.assert_not_called()
    assert json.loads(capsys.readouterr().out)["wallet_name"] == WALLET_NAME


def test_compose_wallet_delegation_is_no_deps_and_preserves_arguments() -> None:
    adapter = ComposeLifecycleAdapter()
    run = MagicMock(
        return_value=MagicMock(
            returncode=0,
            stdout=json.dumps(_lifecycle().to_dict()) + "\n",
            stderr="",
        )
    )
    with patch("subprocess.run", run):
        result = _required_attr(adapter, "create_wallet")(WALLET_NAME, timeout=5.0)

    assert result == _lifecycle()
    command = run.call_args.args[0]
    assert "run" in command
    assert "--rm" in command
    assert "--no-deps" in command
    assert "-T" in command
    assert command[-5:] == ["wallet", "create", "--name", WALLET_NAME, "--json"]
    assert "up" not in command
    assert "start" not in command


def test_compose_rejects_malformed_delegated_wallet_output() -> None:
    adapter = ComposeLifecycleAdapter()
    run = MagicMock(return_value=MagicMock(returncode=0, stdout='{"created":true}\n', stderr=""))
    with (
        patch("subprocess.run", run),
        pytest.raises(errors_module.RpcMalformedResponseError),
    ):
        _required_attr(adapter, "create_wallet")(WALLET_NAME)


def test_cli_failure_leaks_no_raw_wallet_rpc_or_private_identifiers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    conflict = _required_attr(errors_module, "WalletConflictError")
    unsafe = f"{PRIVATE_SENTINEL} {ADDRESS_SENTINEL} /private/path raw-rpc-message"
    with (
        patch(
            "bitheim.infrastructure.compose.adapter.ComposeLifecycleAdapter.create_wallet",
            side_effect=conflict(unsafe),
        ),
        patch("bitheim.interfaces.cli._is_container_execution_context", return_value=False),
    ):
        exit_code = main(["wallet", "create", "--name", WALLET_NAME, "--json"])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert exit_code != 0
    assert captured.out == ""
    assert PRIVATE_SENTINEL not in combined
    assert ADDRESS_SENTINEL not in combined
    assert "/private/path" not in combined
    assert "raw-rpc-message" not in combined
