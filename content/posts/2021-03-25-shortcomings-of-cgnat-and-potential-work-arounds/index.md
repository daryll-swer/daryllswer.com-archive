---
title: "Shortcomings of CGNAT and Potential Workarounds"
slug: "shortcomings-of-cgnat-and-potential-work-arounds"
date: "2021-03-25T11:15:43"
last_modified: "2025-09-28T03:24:17"
canonical_url: "https://www.daryllswer.com/shortcomings-of-cgnat-and-potential-work-arounds/"
wordpress_id: 29
featured_image: "assets/13_DS_Logo_Dark_Mode_SEO-scaled.png"
categories:
  - "Networking"
tags:
  - "CGNAT"
  - "Double NAT"
  - "IPv4"
  - "ISPs"
  - "NAT"
  - "Networking"
---
![Shortcomings of CGNAT and Potential Workarounds](assets/13_DS_Logo_Dark_Mode_SEO-scaled.png)

> **2025 update [here](https://www.daryllswer.com/lets-talk-about-cgnat-and-ipv6-yet-again/).**

This article will mostly focus on the cons of deploying CGNAT and how it ultimately affects the end-user, and what are some of the methods that we can use to improve it.

A quick recap on CGNAT, CGNAT is just a fancy name for NAT whereby an ISP will NAT or map multiple internal IPs (usually the ISP will incorrectly use [RFC1918](https://www.rfc-editor.org/rfc/rfc1918), but ideally should use [RFC6598](https://datatracker.ietf.org/doc/html/rfc6598)) to a single external public IP, i.e., enabling a single public IP to be shared among n number of internal IPs, where each internal IP is assigned to an end-user. Methods used can vary from ISP to ISP, some would just use single source NATs, some would use deterministic NAT etc.

## Shortcomings

1. Breaks P2P traffic.
2. Increases latency (due to TURN).
3. It leads to NAT-keep alive traffic (such as NAT punching, NAT traversal mechanisms etc) on end-users’ local network as well as on the CGNAT device itself.
  
  
  1. Which in theory could affect battery life on end-user devices.
  2. Increased link utilisation/CPU cycles on the CGNAT device.
4. Some end-user applications will simply refuse to work or fail miserably like Xbox Networking (P2P Gaming services), Torrent clients etc.
5. Lacks NAT traversal mechanisms/port forwarding (by default).

Now the IETF published [RFC 7021](https://tools.ietf.org/html/rfc7021) in 2013 which details how CGNAT impacts networking performance and end-user experience, if you want technically backed data and testing methodologies please check that out.

## Workarounds

There are two broad ways to workaround CGNAT cons:

### At ISP Level

1. Do the obvious and [deploy IPv6](https://www.daryllswer.com/ipv6-architecture-and-subnetting-guide-for-network-engineers-and-operators/).
  
  
  - Once IPv6 is deployed, I recommend you remove CGNAT from the network and migrate to [MAP-T](https://www.ripe.net/participate/meetings/open-house/presentations/richard-patterson-sky-italia-and-map-t) in conjunction with point number 2 below.
2. Ensure your CGNAT vendor/configuration is complying with [Endpoint Independent Mapping/Endpoint Independent Filtering](https://www.juniper.net/documentation/us/en/software/junos/interfaces-next-gen-services/topics/concept/app-eim-overview.html#address-pooling-and-endpoint-independent-mapping-for-port-translation__d17021e54) (EIM-NAT). By doing so, you are ensuring that P2P (end-to-end) IPv4 traffic for your customers behind CGNAT will still work, this is the best solution short of migrating 100% to IPv6.
  
  
  - For MikroTik follow the CGNAT section(s) [here](https://www.daryllswer.com/edge-router-bng-optimisation-guide-for-isps/)—Though MikroTik added support for EIM-NAT since RouterOS v7.10, in my testing, it is broken and not up to the mark, hence the original netmap method is still relevant in the article.
3. Ensure [Hairpinning](https://datatracker.ietf.org/doc/html/rfc4787.html#section-6) is enabled on the CGNAT software.
4. Deploy Port Control Protocol [PCP ([RFC 6887](https://tools.ietf.org/html/rfc6887))].
  
  
  - PCP would allow port forwarding to work for end-users behind a CGNAT and hence improve their experience and reduce the visibility of the shortcomings.
  - Needs a Server/Client model, so a client would need to run on end-user’s router/CPE.
    
    
    - Can use OpenWRT with [minimalist-pcproxy](https://github.com/fingon/minimalist-pcproxy) to enable PCP client and PCP connectivity from end-users’ side for a cheap solution.
  - Many vendors like MikroTik (most widely used as a CGNAT device among Indian ISPs) do not support PCP.
  - Lack of awareness among ISPs and network engineers.
  - You can also have a [web dashboard](https://danosproject.atlassian.net/wiki/spaces/DAN/pages/421101573/CGNAT+and+PCP#Introduction) for PCP to permit users to assign their own ports.

### At End User Level

1. Ask your ISP to read this article, tell them to deploy Full-Cone NAT and EIM-NAT configuration on their CGNAT box.
2. Get a public IP from your ISP (most optimal solution).
3. VPN based solution where you route all traffic over the tunnel, including multicast traffic (UPnP).
  
  
  - Many third party platforms exist such as Tailscale, ZeroTier etc.
  - Set up your own VPN/VPS on a Cloud instance with public IP, and then run a VPN client on your home router/client device.

## Conclusion

Even if you properly configured CGNAT with full cone + EIM-NAT, it is still only a plaster solution. The proper solution is to migrate 100% to IPv6, and ensure IPv6 best practices are followed to the letter.

Additionally, for both ISPs and end-users, you can test the quality of your NAT44 (NAT) or NAT444 (CGNAT) configuration using this [tool](https://github.com/HMBSbige/NatTypeTester). If you see EIM-NAT and Full-Cone, then your IPv4 P2P networking will work fine, until you migrate fully to IPv6.
