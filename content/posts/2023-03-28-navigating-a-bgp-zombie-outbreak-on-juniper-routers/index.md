---
title: "Navigating a BGP Zombie Outbreak on Juniper Routers"
slug: "navigating-a-bgp-zombie-outbreak-on-juniper-routers"
date: "2023-03-28T13:18:58"
last_modified: "2025-05-21T01:47:21"
canonical_url: "https://www.daryllswer.com/navigating-a-bgp-zombie-outbreak-on-juniper-routers/"
wordpress_id: 2053
featured_image: "assets/featured.webp"
categories:
  - "DC/Enterprise"
  - "Networking"
tags:
  - "BGP"
  - "Juniper"
  - "JunOS"
---
![Navigating a BGP Zombie Outbreak on Juniper Routers](assets/featured.webp)

**This article has been published on the [APNIC blog](https://blog.apnic.net/2023/04/13/navigating-a-bgp-zombie-outbreak-on-juniper-routers/) as well.**

Border Gateway Protocol (BGP) routing issues in general, can be a headache for network engineers. However, when those issues start exhibiting [zombie-like behaviour](https://labs.ripe.net/author/romain_fontugne/bgp-zombies/), it’s time to take a closer look. This is exactly what I have observed on some Juniper routers in production at [AS48635](https://bgp.tools/as/48635) running as edge routers (responsible for IP Transit, PNIs and IXP peering). This phenomenon is not only perplexing but can also impact traffic engineering efforts or in some rare cases, cause network disruptions.

In this article, I will share my experience with BGP zombie routes on Junos OS (JunOS).

However, please note that **personally** I am not a big Juniper user or fan, my home base has always been FRRouting (Linux) and MikroTik (also Linux with minimal vendor abstraction), so I may not necessarily have complete knowledge of JunOS quirks.

## Background

At AS48635, one of the projects I worked on was cleaning up redundant route objects on IRR and performing route aggregation, that is, exporting only aggregates wherever possible to our external peers.

In our Juniper routers, this translates to:

- Automatic generation of up-to-date prefix lists for our route policies using bgpq3.
- Properly configuring the [route aggregation](https://www.juniper.net/documentation/us/en/software/junos/static-routing/topics/topic-map/config-route-aggregation.html) feature.
- The BGP peer export policy should only export aggregates, even if more specifics exist in the local routing table on a given router.

Below is a real-life configuration sample from one of the affected routers in production to give the readers some context. Please note, only IPv4 config is shared in this article, as IPv6 is identically configured, with the exact same end result (Zombie routes).

```
#Up-to-date aggregate-only prefix list#
policy-options {
    }
    prefix-list as48635-v4 {
        2.57.56.0/22;
        5.157.80.0/21;
    }

#BGP Policy logic#
policy-statement as6453-v4-out {
    term prefixes-out {
        from {
            family inet;
            prefix-list as48635-v4;
        }
        then accept;
    }
    term else-reject {
        then reject;
    }
}

#Route Aggregation#
routing-options {
    aggregate {
        defaults {
            as-path {
                origin igp;
            }
        }
        route 2.57.56.0/22 discard;
        route 5.157.80.0/21 discard;
    }
    generate {
        route 0.0.0.0/0 discard;
    }

#BGP Peer#
group ebgp-6453-v4 {
    type external;
    import [ XYZ ];
    export as6453-v4-out;
    remove-private {
        all;
    }
    peer-as 6453;
    multipath multiple-as;
    neighbor 80.231.152.77 {
        description TATA-v4;
    }
}
```

## Context (Expectation vs Reality)

Based on the configuration sample shared, we expected to only see aggregates and not more-specific routes to be advertised to our peer. However, the following is what we observed:

```
daryllswer@edge-juniper-router> show route advertising-protocol bgp 80.231.152.77   

inet.0: 909266 destinations, 3698169 routes (909000 active, 2 holddown, 317 hidden)
  Prefix		  Nexthop	       MED     Lclpref    AS path
* 2.57.56.0/22            Self                                    I
* 5.157.80.0/21           Self                                    I
* 5.157.80.0/22           Self                                    I
* 5.157.86.0/23           Self                                    I
```

As we can see, for reasons I could not understand, our Juniper router in this example (multiple routers showed the same behaviour) is still exporting more specifics instead of only the aggregates to our peer. I understand from the configuration example shared that the router should only explicitly advertise aggregates, even if more specifics exist in the local table.

## Debugging

The first step I took was to verify the route aggregation was working correctly and indeed it was:

```
daryllswer@edge-juniper-router> show route 2.57.56.0/22 

inet.0: 909307 destinations, 3698305 routes (909043 active, 0 holddown, 317 hidden)
+ = Active Route, - = Last Active, * = Both

2.57.56.0/22       *[Aggregate/130] 1w4d 11:15:19
                      Discard

daryllswer@edge-juniper-router> show route 5.157.80.0/21 

inet.0: 909328 destinations, 3698589 routes (909064 active, 0 holddown, 317 hidden)
+ = Active Route, - = Last Active, * = Both

5.157.80.0/21      *[Aggregate/130] 1w4d 11:19:45
                      Discard
```

The second step I tried was to clear the BGP session with the affected peer(s) (`clear bgp neighbor 80.231.152.77`), but that did not resolve the issue.

The third step I tried was deactivating the BGP peer completely, and then re-enabling it, but that didn’t resolve the issue either.

The fourth step I tried was to verify that no legacy config on the router could be responsible for the issue and config was clean as expected.

```
daryllswer@edge-juniper-router> show configuration | display set | match 5.157.*
set routing-options aggregate route 5.157.80.0/21 discard
set policy-options prefix-list as48635-v4 5.157.80.0/21
```

The final step I tried was a fresh **reboot** on **all** our Juniper edge routers, and voilà! Zombie routes disappeared.

```
daryllswer@edge-juniper-router> show route advertising-protocol bgp 80.231.152.77    

inet.0: 909222 destinations, 3940003 routes (908958 active, 0 holddown, 317 hidden)
  Prefix		  Nexthop	       MED     Lclpref    AS path
* 2.57.56.0/22            Self                                    I
* 5.157.80.0/21           Self                                    I
```

**JunOS versions**:

Different routers ran different JunOS versions and all of them were affected by the same issue. Although of course, these versions may not be the latest recommended versions, it does show that the issue is impacting multiple versions. Versions in use at the time of this issue include:

- 17.3R3.10
- 17.3R3-S7.2
- 18.4R1-S6.3
- 21.4R1-S1.6
- 21.4R3.15

## Conclusion

In my experience working with alternative vendors like MikroTik (RouterOS) for a few years, I have **never** seen a BGP zombie route issue on their platform.

Based on my understanding of the configuration logic, debugging steps taken to resolve the issue and my personal previous experience with alternative vendors, I’m inclined to believe that the issue I have observed is *likely* a Juniper-specific bug, especially based on the fact that a reboot fixed it with no further configuration changes being made.

If this is indeed a Juniper-specific bug, this *could* also mean that a large part of Zombie routes in the Default-free zone (DFZ) could be due to the bug as many Tier 1, 2 and 3 networks (where zombie routes often are propagated) in the world also use Juniper equipment and one wouldn’t expect them to just reboot a router because of Zombie routes, so hence would leave Zombie routes lingering for a long time in the DFZ.

In short, a reboot should **never** be required to remove (or prevent) zombie routes in production.

If someone reading this post is from Juniper or someone with extensive knowledge of JunOS knows what the reason and preventive solution could be for this issue, please feel free to [contact me](https://www.daryllswer.com/contact/) or via any of my professional social media profiles (DMs are open).

### Update, 30th March 2023

Some people have suggested using the ‘from protocol aggregate’ parameter in the policies as a mitigation/workaround. While this could in theory mitigate the issue, it also creates a problem with our internal policy logic because in this case we have downstream BGP customers, and their prefixes are part of as48635-v4 / as48635-v6 prefix list and for obvious reasons, we do not ‘aggregate’ customer prefixes. The as48635-v**X** prefix list is generated based on our AS-SET and hence this workaround isn’t ideal for us.

**At the same time, it still doesn’t answer the question of why a reboot fixed the issue just fine.**
