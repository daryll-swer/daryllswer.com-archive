---
title: "Interesting IPv6 observation on NDP (Neighbour Discovery Protocol)"
slug: "interesting-ipv6-observation-on-ndp-neighbour-discovery-protocol"
date: "2022-12-16T15:04:54"
last_modified: "2025-05-21T01:52:10"
canonical_url: "https://www.daryllswer.com/interesting-ipv6-observation-on-ndp-neighbour-discovery-protocol/"
wordpress_id: 1674
featured_image: "assets/image.png"
categories:
  - "ISP"
  - "IXP"
  - "Networking"
tags:
  - "IPv6"
  - "IXPs"
  - "Networking"
---
![Interesting IPv6 observation on NDP (Neighbour Discovery Protocol)](assets/image.png)

*The following observations and tests were made by me in collaboration with [ExtremeIX](https://extreme-ix.org/) via [AS149794](https://www.daryllswer.com/as149794/).*

**This article has been published on the [APNIC blog](https://blog.apnic.net/2023/01/30/interesting-ipv6-ndp-observation/) as well.**

First, a quick shout out to [Devendra Singh](https://www.linkedin.com/in/devendra-prasad-singh-4ab27854/) (NOC manager of AS132559) and the folks at ExtremeIX who have both collaborated with me in having this non-profit and non-commercial network setup and connectivity for the purpose of research, observations, and improvements.

We will start with a quick primer on Neighbour Discovery Protocol (NDP): It is the IPv6 replacement of ARP in IPv4, it is used for discovering the link-layer addresses of other nodes on the same link, discovering other nodes that are neighbours, and determining the reachability of other nodes. NDP is a key component of IPv6, as it provides the functionality required for a node to determine the link-layer address of its default router and to discover the addresses of other nodes on the local link. It also provides a mechanism for routers to advertise their presence and the services they provide. Overall, NDP plays a crucial role in enabling IPv6 nodes to communicate with each other on a local link and to discover routes to other networks.

There are several RFCs that discuss NDP, but for the purpose of this article, we will refer to [RFC4861](https://www.rfc-editor.org/rfc/rfc4861) and in particular to section [4.3](https://www.rfc-editor.org/rfc/rfc4861#section-4.3) and [4.4](https://www.rfc-editor.org/rfc/rfc4861#section-4.4) which discusses the format used for Neighbour Solicitation (NS) and Neighbour Advertisement (NA).

## Network setup on AS149794

I have a single gigabit L2 path to my upstream provider’s (AS132559) nearest L2 termination switch whereby I send two separately tagged VLANs, one for transit and one for IXP connectivity which in this case is ExtremeIX Bangalore. The hardware is a MikroTik CCR1036-8G-2S+ running RouterOS 7.6 along with a matching version for RouterBOARD firmware.

In my router’s firewall configuration, I use strict firewall rules in the raw table (prerouting chain) and one of those rules is the following:

If a packet has a Global Unicast Address (GUA) source address and the destination address is **not** a GUA [such as link-local addresses (LLA), ULAs etc], drop the traffic.

In my opinion, the above rule, made sense at the time because:

1. I did not see a valid reason to permit traffic originating from external networks to reach my non-GUA addresses whatsoever from a GUA source.
2. The same concept is used in IPv4 with no problems, whereby I drop any packets destined towards [RFC6890](https://www.rfc-editor.org/rfc/rfc6890.html) ranges from external networks where it is from a public address block source.

## The issue

With the firewall rule in place, I started observing that my IPv6 BGP sessions with ExtremeIX’s Route Servers were flapping and unstable. Of course, I have tens of firewall rules in place that are complex and tied together, so it took quite a time to narrow it down to one single rule.

When I realised that disabling the rule, solved the issue with BGP sessions flapping, I decided to dig deeper with WireShark and discovered NDP NS/NA packets where the source address is GUA and the destination address is link-local.

[![](assets/inline/image-3840x1873.png)](assets/image.png)

_Figure-1 (ICMPv6 packets for NDP showing source/destination addresses matching GUA<>LLA pattern)_

## Testing

### On the ExtremeIX side

We initially assumed this GUA<>LLA traffic pattern was vendor/OS specific. The original route server was running CentOS with kernel version 3.10.0. So, we tried to move my peering to an experimental route server (RS) running Linux Kernel version 6.0.6, but that changed absolutely nothing and hence suggested the behaviour is inherent to specific OSes/vendors at the least.

### On my side

I decided to check this out in my own LAN, where I have macOS, iOS, Windows 11, and Debian 11 as hosts on a VLAN, where of course LLA is enabled along with a /64 GUA prefix via SLAAC.

However, even though I observed for over 48 hours with WireShark, and with my hosts/router sending/receiving NA/NS packets 24/7 — I could not find a single packet that matches the GUA<>LLA pattern. All the packets were strictly the LLA<>LLA pattern as I originally expected.

This is where my research led me to RFC4861 sections [4.3](https://www.rfc-editor.org/rfc/rfc4861#section-4.3) and [4.4](https://www.rfc-editor.org/rfc/rfc4861#section-4.4) where I noticed ambiguity. It does not explicitly say whether we can use GUA as the source address/destination for NS and NA when LLA is working as intended. I initially assumed that for NDP NS/NA both source/destination would be only LLA, but as we can see, that’s certainly not the case and hence this behaviour is technically RFC compliant as the RFC is not clear.

## Observations

Since we were unable to replicate the behaviour in my LAN, nor stop the behaviour by upgrading the kernel version on the RS, the folks at ExtremeIX decided to dump traffic from their larger locations where they have tens/hundreds of members connected to gain better insights.

From their traffic dumps, these following were the findings:

1. CentOS (and likely many other Linux distros), Cisco, MikroTik and Huawei showed the GUA<>LLA pattern for NDP.
2. In contrast, vendors like Juniper and Edge-Core, did not show any GUA<>LLA pattern and were instead explicitly only LLA<>LLA.

There is no documentation that we could find to explain why different vendors showed different behaviours.

Based on this [APNIC blog article](https://blog.apnic.net/2019/10/18/how-to-ipv6-neighbor-discovery/) on NDP fundamentals, as per our understanding, it seems to suggest that GUA<>LLA communication in NDP for the purpose of NS/NA is not normal, which, if true, suggests only Juniper/Edge-Core from our findings are following ‘compliant’ or expected behaviour for NDP.

## Conclusion

Although NDP-related communication matching the GUA<>LLA pattern likely should not exist, we can confirm that it does exist in the IPv6 implementation of some vendors.

This does not cause any issues with our observations and this can be considered as just an interesting observation and informative finding.

However, the underlying question remains — why does this behavioural difference exist? While we have not observed inter-vendor issues, that it may occur in certain environments or use cases cannot be entirely ruled out. I believe that this should be documented in the IPv6 Working Group(s) at IETF and the relevant RFCs, which would give solid instructions to vendors about what to do regarding the documented behaviour and prevent possible inter-vendor incompatibility in the future.

I have since modified my firewall rules to permit this behaviour while not compromising the original reason for the firewall rule itself. I have also ensured this firewall rule is reflected in my “Edge Router & BNG Optimisation Guide for ISPs” [article](../2021-06-08-edge-router-bng-optimisation-guide-for-isps/index.md) as well, which contains the technical configuration aspects if you are interested.

Here is the snippet:

```
#Here “bgp_peers” is an address lists containing all the /126s-/127s or /64s used for the peering interfaces with external networks#

/ipv6 firewall raw
add action=accept chain=prerouting comment="Accept all ICMPv6 traffic from BGP peers (Required for LL<>GUA packets)" icmp-options=!154:4-5 in-interface-list=WAN protocol=icmpv6 src-address-list=bgp_peers
```
