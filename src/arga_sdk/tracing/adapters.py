"""Per-client wrappers for stripe-python and google-api-python-client.

No extra provider requests, credential access, module monkey patches or response mutation.
"""

import functools
import inspect
from collections.abc import Mapping

STRIPE_RESOURCES = {"customers", "payment_intents", "charges", "refunds"}
STRIPE_LEGACY = {"Customer": "customers", "PaymentIntent": "payment_intents", "Charge": "charges", "Refund": "refunds"}
STRIPE_VERBS = {"retrieve", "list", "search", "create", "update", "delete"}
GMAIL_VERBS = {"get", "list", "create", "update", "delete", "send", "modify", "trash", "untrash"}


def operation_for(path):
    """Accept canonical tool names too, for customer-side Braintrust normalization."""
    parts = path.split(".")
    if len(parts) == 3:
        provider, resource, verb = parts
        if provider == "stripe" and resource in STRIPE_RESOURCES and verb in STRIPE_VERBS:
            return provider, resource, verb
        if provider == "gmail" and resource in {"messages", "drafts"} and verb in GMAIL_VERBS:
            return provider, resource, verb
        if parts == ["gmail", "profile", "get"]:
            return "gmail", "profile", "get"
    return None


class StripeProxy:
    def __init__(self, target, tracing, path=()):
        self._target, self._tracing, self._path = target, tracing, path

    def __getattr__(self, name):
        target = getattr(self._target, name)
        if name.startswith("_"):
            return target
        path = (*self._path, name)
        if name in STRIPE_LEGACY:
            return StripeProxy(target, self._tracing, path)
        if not callable(target):
            return StripeProxy(target, self._tracing, path) if hasattr(target, "__dict__") else target
        parts = [STRIPE_LEGACY.get(part, part) for part in path if part != "v1"]
        verb = parts[-1].removesuffix("_async")
        operation = operation_for("stripe." + ".".join([*parts[:-1], verb]))

        def parameters(args, kwargs):
            # SDK options may contain headers/keys; only params and explicit known fields are selected later.
            params = dict(kwargs.get("params") or {}) if isinstance(kwargs.get("params"), Mapping) else dict(kwargs)
            if args and isinstance(args[0], str):
                params["id"] = args[0]
            elif args and isinstance(args[0], Mapping):
                params = args[0]
            if len(args) > 1 and isinstance(args[1], Mapping):
                params = {**args[1], **params}
            return params

        if name.endswith("_async") or inspect.iscoroutinefunction(target):

            @functools.wraps(target)
            async def asynchronous(*args, **kwargs):
                return await self._tracing.call_async(target, operation, parameters(args, kwargs), args, kwargs)

            return asynchronous

        @functools.wraps(target)
        def synchronous(*args, **kwargs):
            return self._tracing.call(target, operation, parameters(args, kwargs), args, kwargs)

        return synchronous


class GmailRequest:
    def __init__(self, target, tracing, operation, parameters):
        self._target, self._tracing, self._operation, self._parameters = target, tracing, operation, parameters

    def execute(self, *args, **kwargs):
        return self._tracing.call(self._target.execute, self._operation, self._parameters, args, kwargs)

    def __getattr__(self, name):
        return getattr(self._target, name)


class GmailProxy:
    def __init__(self, target, tracing, path=()):
        self._target, self._tracing, self._path = target, tracing, path

    def __getattr__(self, name):
        target = getattr(self._target, name)
        if name.startswith("_") or not callable(target):
            return target

        @functools.wraps(target)
        def method(*args, **kwargs):
            result = target(*args, **kwargs)
            path = (*self._path, name)
            if hasattr(result, "execute"):
                parts = list(path[1:]) if path and path[0] == "users" else list(path)
                canonical = "gmail.profile.get" if path == ("users", "getProfile") else "gmail." + ".".join(parts)
                return GmailRequest(result, self._tracing, operation_for(canonical), kwargs)
            if name in {"users", "messages", "drafts", "threads", "attachments", "labels", "settings"}:
                return GmailProxy(result, self._tracing, path)
            return result

        return method
