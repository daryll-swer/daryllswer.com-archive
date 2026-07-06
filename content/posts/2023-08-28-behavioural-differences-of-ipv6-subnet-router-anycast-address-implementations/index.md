---
title: "Behavioural differences of IPv6 subnet-router anycast address implementations"
slug: "behavioural-differences-of-ipv6-subnet-router-anycast-address-implementations"
date: "2023-08-28T06:53:42"
last_modified: "2025-05-21T01:47:33"
canonical_url: "https://www.daryllswer.com/behavioural-differences-of-ipv6-subnet-router-anycast-address-implementations/"
wordpress_id: 2739
featured_image: "assets/featured.jpg"
categories:
  - "Networking"
tags:
  - "IPv6"
  - "Networking"
---
![Behavioural differences of IPv6 subnet-router anycast address implementations](assets/featured.jpg)

****This article has been published on the [APNIC blog](https://blog.apnic.net/2023/08/28/behavioural-differences-of-ipv6-subnet-router-anycast-address-implementations/) as well.****

The subnet-router anycast address is a unique IPv6 address that is autoconfigured on a device that *is* a router (meaning `net.ipv6.conf.all.forwarding=1` in Linux context) when the subnet prefix length is [shorter than a /127](https://datatracker.ietf.org/doc/html/rfc6164). In theory, when a host on the subnet/local link sends a packet to this address, it reaches the closest router in the subnet from the host, this can mean the host itself if IPv6 forwarding is enabled. This implies the initial leading zero address of an IPv6 subnet (::) is going to be auto-injected into the host’s (router) local routing table as an address of type anycast. So for example if 2001:db8::/64 is your subnet, then 2001:db8:: is the subnet-router anycast address.

A more [in-depth introduction to the subnet-router anycast](https://web.archive.org/web/20230619150012/https:/into6.com.au/2014/03/30/subnet-router-anycast-addresses-what-are-they-how-do-they-work/) address is available.

Below is an example of a host on my Autonomous System (AS) that I have configured as a ‘router’ via the IPv6 forwarding flag. We can see the subnet-router anycast address being auto-injected into the local routing table of the device.

```
daryll@host1-blr01-as149794:~ $ ip -6 route show table local| grep anycast
anycast 2400:7060:2:100:: dev eth0 proto kernel metric 0 pref medium
anycast 2400:7060:2:102:: dev br-34a147a222f6 proto kernel metric 0 pref medium
anycast fe80:: dev eth0 proto kernel metric 0 pref medium
anycast fe80:: dev veth45d0ffb proto kernel metric 0 pref medium
anycast fe80:: dev br-34a147a222f6 proto kernel metric 0 pref medium
anycast fe80:: dev veth7c6a363 proto kernel metric 0 pref medium
```

## Background

In this article, I do not think it is a matter of RFC compliances per se, at least to my understanding of the relevant RFC(s) for this subject, but it is more about how certain aspects of the anycast address seem to be vaguely implemented on vendors *possibly*****due to vagueness in the RFC(s). The article linked above, mentions that, by default, processes and daemons do not listen on the anycast address. This, however, contradicts my findings, which is the foundation for this article.

I will give a background on how I discovered this contradiction. I subscribe to [Shadowserver](https://www.shadowserver.org/) alerts for my [AS149794](https://www.daryllswer.com/as149794) for exposed ports/services and one day I received email alerts from their platform that notified me some ports were exposed on :: addresses on my network. These addresses live on my edge routers whereby they run the Linux-based MikroTik RouterOS, meaning the underlying network stack is based on the [Netfilter Framework](https://en.wikipedia.org/wiki/Netfilter).

I prefer my edge routers to be **stateless**. Anybody who knows me, knows I like my network backbone/underlay to be stateless. Meaning any packet filtering I do have in place, is done statelessly using the raw table of iptables in the prerouting and output chain on the network underlay.

This means that if, for example, I want to block WAN access to the DNS port on my router, I need to create a prerouting chain rule that drops all traffic from WAN destined towards port 53 TCP/UDP **and** *destination-address-type=local*. And here is where it gets interesting, in the world of IPv4, *dst-*address*-type=local* is sufficient to catch all traffic destined towards IPs sitting on the local device, but not in IPv6, because in the world of IPv6, we have the subnet-router anycast address, which is categorised as a different address type eponymously named [anycast address type](https://ipset.netfilter.org/iptables-extensions.man.html).

So, on my part it was an oversight, I mistakenly assumed that the ‘local’ address type was sufficient to cover both ‘local’ and ‘anycast’ (also, *local* in practice, in my opinion). The solution to fix the exposed ports was simple, I needed to modify my stateless rules to match *dst-address-type=local, anycast* and this worked.

## Linux Netfilter logic vagueness

This is my personal opinion and understanding that not everyone may agree with, and I may be incorrect.

I think the Linux logic of address type differentiation is both useful (especially for stateless filtering) and confusing. For example, when I create a raw prerouting chain rule, whereby I ask it to match against all packets whose dst-IP type is local, I expect it to also match the anycast address by default, because the anycast address **is** **local** on the host (router) that the packet is destined for, but this did not happen.

But now if we use the filter table (input chain), and ask it to drop packets, it will drop so without discriminating between local and anycast, even though the input chain has the parameter support for specifying address types.

So, if the input chain treats anycast as local, why does prerouting chain not treat anycast as local?

I brought up this discussion with my friend [Ammar Zuberi](https://www.linkedin.com/in/ammar-zuberi/) who is a system/low-level programmer more familiar with the Linux Kernel’s underlying network stack and how it all works at the code level than I am. In his opinion, which I echo, the idea of address types in Netfilter has good intentions but a bad implementation, because it leaves room for ambiguity and ambiguity in general does no favour for network implementations or security as evident from my own experience of dealing with address types and other examples in my previous articles.

There is another strange behaviour with anycast addresses on Linux, that I have [mentioned before](https://www.daryllswer.com/how-did-i-set-up-my-own-autonomous-system/#:~:text=Strange%20behaviour%20where,perfectly%C2%A0RFC%20compliant). In summary, let us assume 2001:db8::/64 is our subnet prefix, and we configured 2001:db8::/64 on a router, and we have a host that gets an address via SLAAC from the router (2001:db8::). When we enable IPv6 forwarding on the host, the host will inject the subnet-router anycast address (2001:db8::) into its local routing table. By doing so, the host will no longer be able to reach the actual router because it now shares the same subnet-router anycast address, which also happens to be the IP address configured on the layer 3 interface of the router, and hence IPv6 communication from host<>router or outside world breaks. The only way to avoid this is by configuring 2001:db8::**1**/64 on the router, this ensures the router’s Layer 3 interface has an address that is different from the anycast address.

I honestly do not know if we need to change the existing implementation on Linux at least, update the relevant RFC maybe, or leave it as it is. But what I do know is if the ambiguity caught me in a blind spot, it can certainly catch others out there in a blind spot as well.

## Behavioural Differences Between Vendors

After discovered the exposed anycast addresses on my personal AS and how it works in Linux implementation, I decided to look for a larger sample size in a large production network that consists of Arista, Cisco, Cumulus Linux and Juniper devices to try to figure out if processes and daemons were listening on the anycast address by default.

For this purpose, it was a simple nmap scan against the anycast addresses on these devices for SSH port, as all the devices had SSH listening. I additionally checked for ICMPv6 reachability, as shown in Table 1.

| Vendor | ICMPv6 | Listening on daemons |
| --- | --- | --- |
| Arista | Yes | No |
| Juniper (FreeBSD) | No | No |
| Cisco | Yes | No |
| Linux (Cumulus, MikroTik) | Yes | Yes |

_Table-1 Vendor Behavioural Differences_

Linux-driven OSes like Cumulus Linux (or RouterOS) listens on the anycast address, unless you either configured explicit ACLs, bind the daemon only to specific addresses, or made sure the daemons are [listening only on a MGMT VRF](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux-55/System-Configuration/Authentication-Authorization-and-Accounting/SSH-for-Remote-Access/#ssh-and-vrfs). But even if they are listening only on an MGMT VRF, if there are anycast addresses within that VRF, they would be accessible over the anycast address. Although it is Linux-based, it appears that the default behaviour of listening on the anycast address is not applicable to Arista EOS, perhaps due to vendor abstraction and modifications.

As the number of Cisco devices on the network I checked is limited, I only checked older devices running Cisco IOS 15.1(2)SY9. The behaviour is likely consistent across all Cisco OSes, but I have not personally tested across all of them.

For Juniper, I checked against Junos OS and **not** Junos OS Evolved. Since Junos OS is FreeBSD-based, it is highly possible the behaviour of not listening on the anycast address is inherent on FreeBSD, however I cannot confirm this, as I don’t have access to any production network using FreeBSD nor am I willing to spin up a FreeBSD instance on my personal devices to test this.

If someone reading this article decides to do more thorough testing against more vendors and OSes, I’m happy to update the table with more data.

## Operational Security Implications

The behavioural disparities of subnet-router anycast addresses carry some operational security implications. In Linux environments, where processes listen on the anycast address by default, operational oversights may inadvertently expose services to unintended accessibility. This emphasises the importance of implementing hyper-specific firewall configurations to safeguard against potential vulnerabilities.

Similarly, the variation in ICMPv6 responses across vendors could possibly pose potential challenges in monitoring and diagnosing network issues that we have not foreseen.

## Conclusion

In conclusion, our exploration of subnet-router anycast addresses has shed light on the behavioural differences that exist across various network vendors and operating systems. Understanding these nuances is crucial for network administrators to ensure protection against unintended accessibility or exposure.
