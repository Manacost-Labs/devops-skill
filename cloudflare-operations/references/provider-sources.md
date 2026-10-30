# Cloudflare provider sources

Access/WAF/Tunnel/Workers behavior refreshed: `2026-10-30`. The unchanged DNS/cache/origin baseline below was last reviewed `2026-08-17`; refresh the exact operation again before a live change. Documentation review is not test-account execution evidence.

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

## Detailed sources refreshed for this module revision

| Decision | Official source |
|---|---|
| Access selector/action evaluation | https://developers.cloudflare.com/cloudflare-one/access-controls/policies/ |
| Most-specific application and wildcard/base-path differences | https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/ |
| Application versus reusable policy API ownership | https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/applications/ and https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/policies/ |
| Complete ruleset replacement | https://developers.cloudflare.com/ruleset-engine/rulesets-api/update/ |
| Complete rule definition versus position-only PATCH | https://developers.cloudflare.com/ruleset-engine/rulesets-api/update-rule/ |
| Executing phases and order | https://developers.cloudflare.com/ruleset-engine/reference/phases-list/ |
| Local Tunnel ingress and catch-all | https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/ |
| Remote Tunnel configuration/version | https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/subresources/configurations/ |
| Worker mixed versions and service/DO constraints | https://developers.cloudflare.com/workers/versions-and-deployments/gradual-deployments/ |
| Worker rollback and external resources | https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/ |
| Recent deployments response and active first entry | https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/list/ |

Refresh the exact account/zone endpoint's accepted permission groups with its API page. Do not copy a union of every listed group into a token: choose one minimum applicable read or write permission and exact resources. The optional collector additionally needs the exact zone read for account binding. Its token profile and network permission are supplied by an accountable owner; module metadata does not grant them.

Ruleset and Tunnel updates can create new versions, and Worker rollback creates a new deployment. No source above establishes a generic atomic compare-and-swap API across products. Preserve client-side conflict detection and source-of-truth serialization without claiming unsupported ETag/version preconditions.
