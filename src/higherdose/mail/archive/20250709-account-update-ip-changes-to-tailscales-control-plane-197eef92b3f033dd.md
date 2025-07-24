## Date

Wed, 9 Jul 2025 11:36:28 GMT

## Address

from: Tailscale <no-reply@tailscale.com>
to: springhillroadnet@gmail.com

## Subject

Account update: IP changes to Tailscale’s control plane

## Body

Your firewall policies may require updating.

email header-black ([info.tailscale.com](https://info.tailscale.com/e3t/Ctc/OT+113/d4K34c04/VV-0X22F60qXW2yqlKH2-QlH4W78L4Hk5yNZ7JN3pwdDC3l5QzW6N1vHY6lZ3nxN2t90qKHzNqLW3BFGmt27mvgpW3ySM235w_XQgW7Tvxtr7wsKw4N4j1608ykHfCW6027pg1TstPxN52lg6HVPtvbW2ZC2Sb6Zx4l1W4D-mFv8jZtsgW2fd5Nf4cSZmZN7zhCCTxm6lyW7pxFB47kmlSbW3KxV_b7d-wSXN1GcwWTCxsmDW8wMnsw1zwnbyW3NgyFl2NVXTZW4Ldy1q1l9684V8-wZC8h_-jWW9dkf5Z3xXGcwW54Vztp8H45qVVNcYjN8lcTNFW8SsXsW7_x_Fgf1q-YNY04) )

Account notice:

Your firewall policies may require updating.

This week, we’re making an update to improve the reliability and transparency of Tailscale’s infrastructure. This update may impact your firewall policies. We recommend reviewing and updating any existing firewall rules or policies by Tuesday, July 15 to ensure there are no interruptions in service as the rollout expands.

Over the next few weeks, key control plane services will begin using static IP addresses registered to and managed directly by Tailscale:

-

IPv4: 192.200.0.0/24

-

IPv6: 2606:B740:49::/48

This change affects services like:

-

api.tailscale.com

-

controlplane.tailscale.com

-

login.tailscale.com

Traffic from these services will originate from this predictable and verifiable set of IPs. This should simplify allowlisting, logging, and compliance processes.

Some requests from our control plane already use static IPs. These include SCIM, WebFinger, outbound OIDC flows, and proxy requests to Mullvad’s infrastructure. That will remain unchanged. DERP, log ingestion, and streaming services are not part of this update.

This change is part of our ongoing work to make Tailscale more secure, more predictable, and easier to integrate into your workflows.

Learn more about the update here ([info.tailscale.com](https://info.tailscale.com/e3t/Ctc/OT+113/d4K34c04/VV-0X22F60qXW2yqlKH2-QlH4W78L4Hk5yNZ7JN3pwdDC3l5QzW6N1vHY6lZ3nxN2t90qKHzNqLW3BFGmt27mvgpW3ySM235w_XQgW7Tvxtr7wsKw4N4j1608ykHfCW6027pg1TstPxN52lg6HVPtvbW2ZC2Sb6Zx4l1W4D-mFv8jZtsgW2fd5Nf4cSZmZN7zhCCTxm6lyW7pxFB47kmlSbW3KxV_b7d-wSXN1GcwWTCxsmDW8wMnsw1zwnbyW3NgyFl2NVXTZW4Ldy1q1l9684V8-wZC8h_-jWW9dkf5Z3xXGcwW54Vztp8H45qVVNcYjN8lcTNFW8SsXsW7_x_Fgf1q-YNY04) ) . With any questions, please contact support ([info.tailscale.com](https://info.tailscale.com/e3t/Ctc/OT+113/d4K34c04/VV-0X22F60qXW2yqlKH2-QlH4W78L4Hk5yNZ7JN3pwdDC3l5QzW6N1vHY6lZ3kYW7SpYLr7-zPqyW7Sjc3P918LX6W22k_T76_D3nYW38RSR-4yYtcpW7gB3g88DW3_sW9gzdh12-Cr5gW4t5-yQ7zjD0CN2xSbRRG0gzkW8jF2Dq5dvYWSN64sMmRdjr7PW2N7cpB3Sn82DN7JKdxQVyvWHW3Tgs5Z4Fj0g6W2BV5lG4j2wSZW5HH-6C1rMzq3W3WF-ZJ6yKkG_W2mbkM64Y9kvlW2tNX9v1wFksGVsR-NF3ZNTyMW73c34s7gJWQSV-p6sJ7fH7SrW15HCpl1BLkw8f2WFsv-04) ) .

You are receiving this operational update as a Tailscale user or admin. It relates to the services we provide as part of your existing account, which is why you are receiving it even if you have opted out of Tailscale marketing and promotional emails.

Tailscale Inc., 100 King Street West, Suite 6200, Toronto, Ontario M5X 1B8, Canada
