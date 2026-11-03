# Tailnet-only remote access

Keep every Compose-published port bound to loopback. Use Tailscale Serve on the
host as the only remote ingress, and use a deny-by-default tailnet policy that
allows only the intended phone or user to TCP port 443 on the NVR host. Do not
publish Frigate, Ollama, MQTT, or companion ports on a LAN or public interface.

Frigate uses a local development certificate. On the host running Tailscale,
Serve can terminate a valid tailnet certificate and proxy only to the loopback
backend:

```powershell
tailscale serve --bg --https=443 https+insecure://127.0.0.1:18971
tailscale serve status
```

`https+insecure` applies only to the loopback hop. The phone-to-host connection
still uses Tailscale's encrypted network and the certificate provisioned for the
host's tailnet name. Keep Frigate authentication enabled as a second boundary.

Use Tailscale Grants or ACLs to restrict the listener. This illustrative grant
uses placeholders deliberately; replace them with the phone and NVR tailnet
addresses or reviewed device/user selectors:

```json
{
  "grants": [
    {
      "src": ["<phone-tailnet-ip>/32"],
      "dst": ["<nvr-tailnet-ip>/32"],
      "ip": ["tcp:443"]
    }
  ]
}
```

Remove broad allow-all rules that would also reach the NVR, validate the policy
with Tailscale's policy tests, and confirm access fails from an unapproved device.
Use stable tailnet identity/address selectors rather than a phone carrier's
changing public IP address.

Use Tailscale **Serve**, not **Funnel**. Funnel intentionally exposes a service
to the public internet and bypasses this design goal. Do not enable advertised
subnet routes, exit-node service, Tailscale SSH, or the web client unless each is
separately required and reviewed. Periodically verify Serve status, tailnet
policy, device ownership, key expiry, client updates, and that only TCP 443 is
allowed to the NVR host.

References: [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve),
[Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve), and
[Grants](https://tailscale.com/docs/features/access-control/grants).
