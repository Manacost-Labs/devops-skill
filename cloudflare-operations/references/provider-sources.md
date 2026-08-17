# Cloudflare provider sources

Last verified: `2026-08-17`

Use only official Cloudflare documentation and API references for provider behavior. Re-check these sources before execution when permissions, limits, API fields, product availability, or dashboard paths matter.

| Area | Official source |
|---|---|
| DNS record management | https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/ |
| DNS Records API | https://developers.cloudflare.com/api/resources/dns/subresources/records/ |
| Cache purge API | https://developers.cloudflare.com/api/resources/cache/methods/purge/ |
| WAF custom rules | https://developers.cloudflare.com/waf/custom-rules/ |
| WAF phases | https://developers.cloudflare.com/waf/reference/phases/ |
| Rate limiting rules | https://developers.cloudflare.com/waf/rate-limiting-rules/ |
| Access policies | https://developers.cloudflare.com/cloudflare-one/access-controls/policies/ |
| Cloudflare Tunnel | https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/ |
| Workers versions/deployments | https://developers.cloudflare.com/workers/versions-and-deployments/ |
| Protect origin server | https://developers.cloudflare.com/fundamentals/security/protect-your-origin-server/ |
| Authenticated Origin Pulls | https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/ |
| Cloudflare IP addresses | https://developers.cloudflare.com/fundamentals/concepts/cloudflare-ip-addresses/ |

Current facts to preserve in plans:

- WAF custom rules, managed rules, and rate limiting use ordered Ruleset Engine phases; editing a ruleset can affect behavior beyond one expression.
- Access policies are default-deny, while `Bypass` disables Access enforcement and logging for matching traffic.
- Tunnel connectors establish outbound-only connectivity, but route and ingress changes can still expose or interrupt applications.
- A Worker version captures code, assets, bindings, and compatibility settings; it does not version external storage state.
- Cache purge supports granular URL and, where available, tag/host/prefix scopes; purge-everything is materially broader.
