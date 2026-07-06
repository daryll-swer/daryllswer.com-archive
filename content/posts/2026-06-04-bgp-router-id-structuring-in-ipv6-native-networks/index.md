---
title: "BGP Router ID Structuring in IPv6 Native Networks"
slug: "bgp-router-id-structuring-in-ipv6-native-networks"
date: "2026-06-04T14:36:35"
last_modified: "2026-06-14T05:55:24"
canonical_url: "https://www.daryllswer.com/bgp-router-id-structuring-in-ipv6-native-networks/"
wordpress_id: 5324
featured_image: "assets/BGP_RouterID_FT-scaled.jpg"
categories:
  - "Architecture"
  - "Networking"
tags:
  - "BGP"
  - "IPv6"
---
![BGP Router ID Structuring in IPv6 Native Networks](assets/BGP_RouterID_FT-scaled.jpg)

At [Swer Networks](https://swernetworks.com), we design and implement scalable, future-ready IPv6 architectures for our clients. This includes everything from tailoring [geographical addressing models](https://www.daryllswer.com/ipv6-architecture-and-subnetting-guide-for-network-engineers-and-operators/) to the structuring of Border Gateway Protocol (BGP) Router IDs in modern networks. In this post, we focus specifically on the design and structuring of BGP Router IDs within IPv6-native environments.

## Introduction

BGP Router ID is also formally known as BGP Identifier, which was first defined in [RFC 4271](https://datatracker.ietf.org/doc/html/rfc4271#section-1.1), quoted below.

> A 4-octet unsigned integer that indicates the BGP Identifier of the sender of BGP messages. A given BGP speaker sets the value of its BGP Identifier to an **IP address assigned to that BGP speaker**. The value of the BGP Identifier is determined upon startup and is the same for every local interface and BGP peer.
>
>
>
>
>
>
>
> — [RFC 4271, Section 1.1](https://datatracker.ietf.org/doc/html/rfc4271#section-1.1)

RFC 4271 states that the BGP Router ID is an IP address that is assigned to a local interface on a given BGP speaker. Over the years, this led to the common practice of having a legacy /32 IPv4 address assigned to the loopback interface, and that loopback IPv4 address is then used in the BGP configuration templates, and the practice of pinging or tracerouting to the loopback /32 IPv4 address became common.

It’s important to note that this older RFC and practice over the years led to network engineers making the ‘permanent’ assumption that BGP Router ID is the equivalent of an IPv4 address, and said IP address must be reachable on some local interface of a BGP speaker.

## Implications for IPv6 Native Networks

However, when we deploy IPv6 native networks, there is no IPv4 configuration on the underlay services and policies, meaning Point-to-Point (PtP) links only have IPv6 addressing or IPv6 unnumbered addressing with link-local. Loopback only has a /128 Global Unicast Address (GUA), and any customer services requiring IPv4 are routed over [RFC 8950](https://datatracker.ietf.org/doc/html/rfc8950), which means purely IPv6 next hops in the routing table.

So the question arises — how do we handle BGP Router ID numbering structure in IPv6 native networks?

[RFC 6286](https://datatracker.ietf.org/doc/html/rfc6286#section-2.1) revised the definition of BGP Identifier to the following:

> The BGP Identifier is a 4-octet, unsigned, non-zero integer that should be unique within an AS. The value of the BGP Identifier for a BGP speaker is determined on startup and is the same for every local interface and every BGP peer.
>
>
>
>
>
>
>
> — [RFC 6286, Section 2.1](https://datatracker.ietf.org/doc/html/rfc6286#section-2.1)

It’s now clear that the BGP Router ID is no longer an IPv4 address in any meaningful sense. There’s a familiar saying: ‘If it looks like a duck, swims like a duck, and quacks like a duck, then it’s probably a duck.’

With RFC 6286, however, the situation becomes more like: ‘It looks like a duck, but it doesn’t swim, doesn’t quack, and definitely isn’t a duck.’

In fact, the RFC explicitly states that the shift was driven by the needs of IPv6‑only networks, where relying on an IPv4 address for an identifier was no longer viable:

> To accommodate situations where the current requirements for the BGP Identifier are not met (such as in the case of an **IPv6-only network**), this document relaxes the definition of the BGP Identifier to be a 4-octet, unsigned, non-zero integer and relaxes the “uniqueness” requirement so that only AS-wide uniqueness of the BGP Identifiers is required. These revisions to the base BGP specification do not  
> introduce any backward compatibility issues.
>
>
>
>
>
>
>
> — [RFC 6286, Section 1](https://datatracker.ietf.org/doc/html/rfc6286#section-1)

So now that we have established both the original and revised definitions of BGP Router ID, there are different ways based on client-specific needs for structuring the 4-octet unsigned, **non-zero integer** with quad-dotted notation.

## Example of BGP Router ID Structuring

The Router ID ranges from 0.0.0.1 (zero integer is excluded) to 255.255.255.255. Using the same maths for calculating the number of IPv4 addresses (232), there are 4,294,967,295 (1 is subtracted by excluding zero integer) possible unique BGP Router IDs in an organisation. Now, just like legacy IPv4 [RFC1918](https://datatracker.ietf.org/doc/html/rfc1918) space, the risk of overlap (collision) across AS (organisation) boundaries is possible, which, fortunately, has already been addressed as follows:

> If the BGP Identifiers of the peers involved in the connection collision are identical, then the connection initiated by the BGP speaker with the larger AS number is preserved.
>
>
>
>
>
>
>
> — [RFC 6286, Section 2.3](https://datatracker.ietf.org/doc/html/rfc6286#section-2.3)

At Swer Networks, we prefer to inject some logic into the individual ‘octets’ (segments in IPv6) to improve human readability and comprehension during real-life operations of a network. For example, the Router ID’s basic structure is A.B.C.D; we assign a meaning to each of these octets (the meaning will vary from organisation to organisation), as demonstrated below.

A.B.C.D, where:

- A → Represents a hierarchical network (device) function code (like a PE router, or P router, or BNG, etc.).
- B → Represents a tenant region or is reserved for future use, with a default value of zero.
- C–D → Represents a 16-bit instance ID, allowing up to 512 unique IDs per Function Code A.

This means, for example, if A=3 and B=0, then for function 3, C – D gives us 512 possible instances of the Router ID, meaning 65,536 possible BGP routers in an organisation matching the function code A=3.

To help visualise this, Table 1 is an example table of what this *could* look like in production.

| Function code (A) | Function name | Tenant/reserved (B) | Router ID range (C–D) |
| --- | --- | --- | --- |
| 0 | Lab/test/R&D | 0 | 0.0.0.1 – 0.0.255.255 |
| 1 | DFZ-Facing PE routers | 0 | 1.0.0.0 – 1.0.255.255 |
| 2 | P routers | 0 | 2.0.0.0 – 2.0.255.255 |
| 3 | DIA/IP Transit customer-facing PE Routers | 0 | 3.0.0.0 – 3.0.255.255 |
| 4 | NNI/UNI-facing PE Routers | 0 | 4.0.0.0 – 4.0.255.255 |

_Table-1 Router ID Structure example_

## IGP Operational Simplicity

As a side bonus of the structured BGP Router ID numbering schema, the same schema can be used for your Interior Gateway Protocol’s (IGP’s) local ID, for both OSPFv3 Router ID and for IS-IS system ID, that is, there is no /32 IPv4 address on the loopback interface of a router.

## What about troubleshooting?

Assuming your network vendor’s software implementation is 100% compliant with RFC 6286 and has no bugs impacting BGP with the **not**-IPv4 router ID, you may be used to relying on ping/traceroute towards the /32 IPv4 loopback IP, but since we are discussing IPv6 native networks, the answer is you ping/traceroute towards the /128 IPv6 loopback IP for troubleshooting, as IPv6, anyway, will be responsible for next-hop routing of IPv4.

**Quick tip**: As with [OOB network design](https://www.daryllswer.com/out-of-band-network-design-for-service-provider-networks/#dns-and-loopback-addressing), we recommend you use structured DNS schemas for easy memory of IPv6 loopback endpoints.

With IGP, as long as your OSPFv3 implementation is compliant with [RFC7503](https://www.rfc-editor.org/rfc/rfc7503#section-5), it should work as intended. As for IS-IS, it works using Connectionless-mode Network Service (CLNS), so it does not matter either way.

That said, you should exercise caution and double-check with your vendor on the software support for truly IPv6-only loopbacks; some implementations of BGP SR-TE, for example, may not support IPv6-only loopbacks and require /32 IPv4 loopbacks.

## Conclusion

There are different ways to design a Router ID numbering scheme to suit your needs. Alternatively, you can also have no structured numbering at all if your network infrastructure is 100% orchestrated and automated via a CI/CD pipeline. In such cases, software systems dynamically assign and track Router IDs, with algorithms determining allocation and maintaining state, effectively removing the need for manual overhead from the human layer.
