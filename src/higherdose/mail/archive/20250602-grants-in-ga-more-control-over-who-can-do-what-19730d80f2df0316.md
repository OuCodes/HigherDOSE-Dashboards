## Date

Mon, 2 Jun 2025 13:32:02 GMT

## Address

from: Tailscale <hello@tailscale.com>
to: springhillroadnet@gmail.com

## Subject

Grants in GA: More control over who can do what

## Body

Implement least-privilege access with more precision.

Hi Springhill,

Exciting news! Grants ([info.tailscale.com](https://info.tailscale.com/e3t/Ctc/OT+113/d4K34c04/VW1j0-8VyGVbW87fddt3RgRNpV3Z50p5xjRsqN2v9B1-3l5QzW6N1vHY6lZ3nlW98xv-r7WBDWcT1QZ21tGWyqV-fdyH16ZM9rW7f0Msp671NHNW4btm-Q3J--y0W5Q5Sj86KXbDVW7F2Yqs4j2RGGW8JB7-s7xg1h9N2mJkZyJPDnnW6m8wPL4_JSL-W743PrL4JSnVzW7cVNwr5zy7hHN4yqY_6fsq-KW2BkLXr8D-BswW3HsSRt5tYgt1W40fvYw4QPmWSN6Nw--nM2R6-W8sbTQX2yq81QW1zP3s543mcKCW6CvQWV5N76DpW1Q0G0h4YYBVhW1J5wn88yp7H3f78wk3l04) ) are now generally available 🎉

Grants extend the power of ACLs by letting you define not just which users or devices can access a resource, but also what they’re allowed to do once they’re connected.

Think of it as ACLs, evolved:

-

Combine network and application-layer permissions in the same tailnet policy file

-

Define custom routing configurations with Via ([info.tailscale.com](https://info.tailscale.com/e3t/Ctc/OT+113/d4K34c04/VW1j0-8VyGVbW87fddt3RgRNpV3Z50p5xjRsqN2v9B1H3l5QzW69sMD-6lZ3lpW55yhfs5h-tQ0N7FT1ZN9nXpvN6vVrNkBvl59W4TjxnT8bhVKkN4qt2M9by0pmW23C_rS7r0jx_W5mKcbg42PhB2Tj0Nj5PDYpWW1mTlbP1jbDGmW4_bLbJ58qtnNN7_RNx1ZH0l6N13sWv0Ys1j7W7NYyr17nMhzlN8qMlT63Gp8BW4zvcg33VGLYfW1HtBsl8WG1LFW1_Bx5v1y5VCbW2ZWKJ33HXMqTW6t1d4_6kSX0rW6zzrdT7bXQv_f5rlLkT04) )

-

Follow the same deny-by-default model you already use

With Grants, you can:

✅ Allow users to connect to a service but only read, not write

✅ Limit a CI job to run specific API calls instead of granting full access

✅ Give contractors restricted access to a subset of actions on internal tools

Grants help IT and security teams implement least-privilege access with more precision. You get more control without changing how you manage your policies. The syntax is familiar, and the learning curve is minimal.

Learn more →
([info.tailscale.com](https://info.tailscale.com/e3t/Ctc/OT+113/d4K34c04/VW1j0-8VyGVbW87fddt3RgRNpV3Z50p5xjRsqN2v9B1-3l5QzW6N1vHY6lZ3nlW98xv-r7WBDWcT1QZ21tGWyqV-fdyH16ZM9rW7f0Msp671NHNW4btm-Q3J--y0W5Q5Sj86KXbDVW7F2Yqs4j2RGGW8JB7-s7xg1h9N2mJkZyJPDnnW6m8wPL4_JSL-W743PrL4JSnVzW7cVNwr5zy7hHN4yqY_6fsq-KW2BkLXr8D-BswW3HsSRt5tYgt1W40fvYw4QPmWSN6Nw--nM2R6-W8sbTQX2yq81QW1zP3s543mcKCW6CvQWV5N76DpW1Q0G0h4YYBVhW1J5wn88yp7H3f78wk3l04) )

Start exploring →
([info.tailscale.com](https://info.tailscale.com/e3t/Ctc/OT+113/d4K34c04/VW1j0-8VyGVbW87fddt3RgRNpV3Z50p5xjRsqN2v9B1-3l5QzW6N1vHY6lZ3mMW8rVF4q5SLBMYW2x62x34trDF1W6-r6BY3yhPJnW71T5Pv3BR9zGVKPvZY7YmQPGVhmhnJ5l7rm1VC_pRJ4Mk54HW6XCg658mYjv8W5-vlqp89125_W3B9LWL6_x1p0W7WMpPW4BcDsVV7BqQ01g08X7W4PmWBG6tzXs3W3kCf-r61YFFkW3ddTXx6tyYPFW8sXvqd5MCwPBW6nRy1v5vYs_zW75sS6j7vNZs3V1H_vW8XmcmSN85SLl31N35VW41P26S6RsKR4W2PWSmw1222cnf6t6RXv04) )

If you're using first-generation ACLs in your policy file today, don't worry – these ACLs aren't being deprecated. Tailscale is committed to backwards compatibility and we will not require you to update these rules to the new Grants syntax. You can migrate at your own pace, when and if it makes sense for your organization.

– The Tailscale Team

© Tailscale Inc.  ([info.tailscale.com](https://info.tailscale.com/e3t/Ctc/OT+113/d4K34c04/VW1j0-8VyGVbW87fddt3RgRNpV3Z50p5xjRsqN2v9B1H3l5QzW69sMD-6lZ3p6W1BG77q3mZjbcW57MY5v8wt-19W3tw2hw2TlNL_N7_NRf1Lv5mWW72pGFv594N2xW7-32tT45vj4_VHt95F3h2bCNW4-dNQj65xHRGW2GHRzW5wCYJ9VYkscS65r4czW7_vGdN8dTJk7W32cscM7yxWXjW7WmQLM2msjrzW2vgZ1926NjcjW6dFBKL36hQMCW2MFGPt9h9620MKdkKj84pmhW5hLgTT8bd0bjW7xvgl17bD9pMW5Q2nHM4NKSYFf1yW7pK04) )

Tailscale Inc., 100 King Street West, Suite 6200, Toronto, Ontario, M5X 1B8, Canada

If you no longer wish to receive marketing emails from Tailscale, you can adjust your preferences ([info.tailscale.com](https://info.tailscale.com/hs/preferences-center/en/page?data=W2nXS-N30h-B0W4rwSRw2sVQDhW38c32L41W14tW2WnNGQ2KQt1_W3-0jwy2-LynHW2FFMqz1ZpG4NW2r34FW45Hq2hW1-X7QR3gbPJRW4ms-rw23mm1tW2Tz8dY3Cf5VCW41Br4G3b46TwW3bgZLd24TwpNW3JYMGQ4mvCqyW4rwW164kgnB9W2309ZX2Rywp-W3dj38Z2-m6gFW1VpDbk4cBBxtW43rc6d1Nh7hbW45PDkm2HT9GRW43DdTy45TRs7W2zz8ll3ZD3C1W4mlgRc4tl4PvW3BVY6z45Fl1RW3dpqTd2KPGdTW1SqhWp30yHd5W30CfPD3jdKc6W4mJ0yf2vXJqMW1BKj9N2FvS2NW3bfHnF43PQ8JW2PBM_R1Vbq6yW1Lywtp4rnQ3NW3Zw8hF38n5lDW2HCrsB3dz8RCW4mLv-12Htj8FW2p0ryt43pdgcW4pmmRK2YvTWdW45kb-S1QBGdcW2-dX0y3N-LB0W34CD9t3QxRTkW43s6KF1Sl6Q6W1BmY3l2MXtjZW4cs8Jx2RB-vGW3M4SwM2PP9YvW3T3Nh4213J8NW49QXhh3LXh1QW2q_pDR2vMZt8W4mz04h34GBB3f4m98MJ04&_hsenc=p2ANqtz-9hKGRol5L2-3uJ4wyfVQmmHygtDtvscoK6mZsvfAxSxbdbsdWRGRp4FQr495WcRLutscQcq4cig4EFfC-u7n7Obq63hExzdBDYVpK82SKkuzvW6kk&_hsmi=364290151) ) or unsubscribe ([info.tailscale.com](https://info.tailscale.com/hs/preferences-center/en/direct?data=W2nXS-N30h-B0W4rwSRw2sVQDhW38c32L41W14tW2WnNGQ2KQt1_W3-0jwy2-LynHW2FFMqz1ZpG4NW2r34FW45Hq2hW1-X7QR3gbPJRW4ms-rw23mm1tW2Tz8dY3Cf5VCW41Br4G3b46TwW3bgZLd24TwpNW3JYMGQ4mvCqyW4rwW164kgnB9W2309ZX2Rywp-W3dj38Z2-m6gFW1VpDbk4cBBxtW43rc6d1Nh7hbW45PDkm2HT9GRW43DdTy45TRs7W2zz8ll3ZD3C1W4mlgRc4tl4PvW3BVY6z45Fl1RW3dpqTd2KPGdTW1SqhWp30yHd5W30CfPD3jdKc6W4mJ0yf2vXJqMW1BKj9N2FvS2NW3bfHnF43PQ8JW2PBM_R1Vbq6yW1Lywtp4rnQ3NW3Zw8hF38n5lDW2HCrsB3dz8RCW4mLv-12Htj8FW2p0ryt43pdgcW4pmmRK2YvTWdW45kb-S1QBGdcW2-dX0y3N-LB0W34CD9t3QxRTkW43s6KF1Sl6Q6W1BmY3l2MXtjZW4cs8Jx2RB-vGW3M4SwM2PP9YvW3T3Nh4213J8NW49QXhh3LXh1QW2q_pDR2vMZt8W4mz04h34GBB3f4m98MJ04&_hsenc=p2ANqtz-9hKGRol5L2-3uJ4wyfVQmmHygtDtvscoK6mZsvfAxSxbdbsdWRGRp4FQr495WcRLutscQcq4cig4EFfC-u7n7Obq63hExzdBDYVpK82SKkuzvW6kk&_hsmi=364290151) )  here.
