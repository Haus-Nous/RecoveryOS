"""Developer and Diagnostic CLI for Payment Providers.

CRITICAL SECURITY REQUIREMENT:
This CLI NEVER accepts raw API keys or secrets as command-line arguments.
Credentials must be resolved exclusively via server-controlled allowlisted aliases
(e.g., RAZORPAY_TEST_DEMO).
"""

import argparse
import asyncio
import json
import sys
from typing import Any

from app.application.ports.provider_credentials import ProviderCredentials
from app.application.ports.unit_of_work import UnitOfWork
from app.application.services.provider_service import (
    PaymentProviderRegistry,
    PaymentProviderService,
)
from app.domain.types import MerchantId
from app.infrastructure.database import get_session_factory
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.credential_resolver import EnvProviderCredentialResolver
from app.providers.errors import ProviderError
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderConnectionStatus,
    ProviderCreateOrderRequest,
    ProviderMode,
)


def _get_default_service() -> PaymentProviderService:
    session_factory = get_session_factory()

    def uow_factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    credential_resolver = EnvProviderCredentialResolver()
    return PaymentProviderService(
        uow_factory=uow_factory,
        credential_resolver=credential_resolver,
    )


async def run_verify(args: argparse.Namespace) -> int:
    service = _get_default_service()
    try:
        if args.connection_id:
            result = await service.verify_connection(
                merchant_id=MerchantId(args.merchant_id),
                connection_id=args.connection_id,
            )
        else:
            # Standalone diagnostic verification with allowlisted alias
            resolver = EnvProviderCredentialResolver()
            dummy_conn = PaymentProviderConnection(
                id="diagnostic_cli",
                merchant_id=MerchantId(args.merchant_id or "cli_diagnostic"),
                provider=PaymentProviderName.RAZORPAY,
                mode=ProviderMode.TEST,
                credential_ref=args.credential_ref,
                status=ProviderConnectionStatus.UNVERIFIED,
            )
            creds: ProviderCredentials = await resolver.resolve(dummy_conn)
            registry = PaymentProviderRegistry()
            provider = registry.get_provider(dummy_conn, creds)
            result = await provider.verify_connection()

        output: dict[str, Any] = {
            "status": "SUCCESS" if result.is_valid else "FAILED",
            "provider": result.provider.value,
            "mode": result.mode.value,
            "key_id_fingerprint": result.key_id_fingerprint,
            "verified_at": result.verified_at.isoformat(),
            "message": result.message,
        }
        print(json.dumps(output, indent=2))
        return 0 if result.is_valid else 1
    except ProviderError as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)}, indent=2
            ),
            file=sys.stderr,
        )
        return 1


async def run_create_test_order(args: argparse.Namespace) -> int:
    service = _get_default_service()
    try:
        order = await service.create_test_order(
            merchant_id=MerchantId(args.merchant_id),
            connection_id=args.connection_id,
            request=ProviderCreateOrderRequest(
                amount_minor=args.amount_minor,
                currency=args.currency,
                receipt=args.receipt,
                notes=json.loads(args.notes) if args.notes else {},
            ),
        )
        print(json.dumps(order.model_dump(mode="json"), indent=2))
        return 0
    except ProviderError as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)}, indent=2
            ),
            file=sys.stderr,
        )
        return 1


async def run_fetch_order(args: argparse.Namespace) -> int:
    service = _get_default_service()
    try:
        order = await service.fetch_order(
            merchant_id=MerchantId(args.merchant_id),
            connection_id=args.connection_id,
            provider_order_id=args.order_id,
        )
        print(json.dumps(order.model_dump(mode="json"), indent=2))
        return 0
    except ProviderError as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)}, indent=2
            ),
            file=sys.stderr,
        )
        return 1


async def run_fetch_payment(args: argparse.Namespace) -> int:
    service = _get_default_service()
    try:
        payment = await service.fetch_payment(
            merchant_id=MerchantId(args.merchant_id),
            connection_id=args.connection_id,
            provider_payment_id=args.payment_id,
        )
        print(json.dumps(payment.model_dump(mode="json"), indent=2))
        return 0
    except ProviderError as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)}, indent=2
            ),
            file=sys.stderr,
        )
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recoveryos-provider",
        description="RecoveryOS Payment Provider Diagnostic CLI (Strictly Test Mode)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # verify
    verify_p = subparsers.add_parser("verify", help="Verify connection or credential alias")
    verify_p.add_argument("--merchant-id", default="m_default", help="Merchant ID")
    verify_p.add_argument("--connection-id", help="Existing connection ID to verify")
    verify_p.add_argument(
        "--credential-ref", default="RAZORPAY_TEST_DEMO", help="Allowlisted credential alias"
    )

    # create-test-order
    order_p = subparsers.add_parser("create-test-order", help="Create a test order")
    order_p.add_argument("--merchant-id", required=True, help="Merchant ID")
    order_p.add_argument("--connection-id", required=True, help="Connection ID")
    order_p.add_argument(
        "--amount-minor", required=True, type=int, help="Amount in minor units (paise)"
    )
    order_p.add_argument("--currency", default="INR", help="Currency (e.g. INR)")
    order_p.add_argument("--receipt", required=True, help="Unique receipt identifier")
    order_p.add_argument("--notes", help="JSON notes dict")

    # fetch-order
    fetch_o_p = subparsers.add_parser("fetch-order", help="Fetch an order by ID")
    fetch_o_p.add_argument("--merchant-id", required=True, help="Merchant ID")
    fetch_o_p.add_argument("--connection-id", required=True, help="Connection ID")
    fetch_o_p.add_argument("--order-id", required=True, help="Provider order ID")

    # fetch-payment
    fetch_p_p = subparsers.add_parser("fetch-payment", help="Fetch a payment by ID")
    fetch_p_p.add_argument("--merchant-id", required=True, help="Merchant ID")
    fetch_p_p.add_argument("--connection-id", required=True, help="Connection ID")
    fetch_p_p.add_argument("--payment-id", required=True, help="Provider payment ID")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    if args.command == "verify":
        sys.exit(loop.run_until_complete(run_verify(args)))
    elif args.command == "create-test-order":
        sys.exit(loop.run_until_complete(run_create_test_order(args)))
    elif args.command == "fetch-order":
        sys.exit(loop.run_until_complete(run_fetch_order(args)))
    elif args.command == "fetch-payment":
        sys.exit(loop.run_until_complete(run_fetch_payment(args)))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
