---
title: "The Human Side of ISPs"
slug: "the-human-side-of-isps"
date: "2021-08-28T01:50:13"
last_modified: "2025-05-21T01:47:31"
canonical_url: "https://www.daryllswer.com/the-human-side-of-isps/"
wordpress_id: 558
featured_image: "assets/Computer-with-people.png"
categories:
  - "ISP"
  - "Networking"
tags:
  - "ISPs"
  - "Networking"
---
![The Human Side of ISPs](assets/Computer-with-people.png)

We spend a lot of time examining the technical problems that can occur at Internet Service Providers (ISPs), but relatively little time looking at the most important element of all — the people actually working at them.

In this post, I want to discuss the challenges and difficulties faced by the people working in ISPs. I am going to focus on experiences from ISPs in India, but I would emphasize that these problems may not be confined to India alone. I think that by discussing these issues, we can get to work on improving them.

First, there are a few caveats to get out of the way.

My background is in giving best practice guidance to network engineers. I haven’t had a lot of experience working in an ISP myself, but I work closely with a lot of people who do. The points raised in this post are based on my discussions with ISP proprietors and network engineers with years of experience. I work with their network infrastructure sometimes, however, these arrangements are based on mutual trust without any financial transactions occurring.

I also want to point out that India is a big place, and conditions at ISPs will vary, so this post may not reflect everyone’s experience. For this reason, I encourage people to share their own experiences in the comments so we can all learn more.

## It’s a tough job, and burnout is common

It is crucial to remember that even if a human operator is good at their job, they are not immune to the [burnout effect](https://www.siliconrepublic.com/advice/anneka-burrett-brighthr-burnout), which, of course, applies to the ISP world. Running a network can be stressful, and that has implications for the mental health of the people who work there.

### Pay scale/work conditions

In a typical Indian ISP, the working conditions simply do not match the pay grade.

A few examples based on people I talked to who currently work in ISPs as of 2021:

- A person may work 7 days a week for a measly USD 200 (approximately) monthly salary for a year (or more) and may not get a pay grade increase, if ever at all.
- A person may work for an ISP for 5+ years and still not get a monthly salary greater than USD 336.
- A person with a college/University degree in Computer Science Engineering (or similar fields) would typically join an ISP, work for a few months (maybe a year or two) for the experience and move on for reasons stated above
- Or simply a person may [not](https://www.financialexpress.com/industry/bsnl-fails-to-pay-may-salary-to-staff/2004176/) get their salary on time

Their workload includes provisioning, troubleshooting, handling phone calls all day related to customers, last-mile issues and power issues, among other things.

They work a lot more than the typical 9 am – 5 pm. One of the engineers that I talked to works from 9 am to 7 pm, Monday to Friday, with an extra workload on Saturday. All of this in a room that is hot from networking equipment, no fancy air conditioning, and out in the hot sun when dealing with last-mile issues.

To make things more difficult, many ISPs lack a ticketing system, which results in difficulty for the staff to keep track of issues.

So, when problems occur, is it appropriate to blame the network engineer/operator for mistakes or not having up to date knowledge? Sure, sometimes you might get ones who have decent salaries and just don’t care, but in many cases, they’re simply overworked. It is helpful to consider that some may be more concerned with providing for their families with their very low income, than pumping out next-gen solutions like a truly open-source network backbone.

That being said, the lack of and access to quality education/training is one of the core reasons why we have underperforming network engineers, to begin with.

With such burnout-inducing work conditions, the operators simply cannot get the time required to learn, develop personally and professionally, nor have ample free time for personal use and leisure, all of which results in bad networks and rushed deployments.

## Contributing factors to low salaries

An ISP can only pay its employees according to the revenue it brings in, and this revenue depends on what it charges customers. When customers have an expectation of unrealistically low prices, and ISPs try to meet those expectations, the costs have to be cut somewhere.

And unfortunately, the salaries of workers can be one of the first things to be cut. Below are some contributing factors that were raised in my discussions with network operators:

- Predatory pricing from big telcos
  
  
  - For example, an operator may offer 1GB of data at INR 0.21 (USD 0.0028) where 1GB data is offered to mobile subscriber at INR 5 to 7 (USD 0.067 to 0.094) per GB by the same operator
- Continuous pricing pressure compels small players to opt for cheap and unreliable hardware
- A strange obsession with providing a voice bundle to home users where 99% don’t use it, as we live in the age of VoIP such as WhatsApp or simply VoWiFi
- The inaction of small players on policy issues
- The need to compete with extremely cheap plans such as INR 167 monthly for 200Mbps
  
  
  - When the package is too cheap, which is the case here, there will be a lot of compromise in end-to-end delivery
  - This in turn drives the owner/management of the ISP to make hard decisions on paying less to the employees
- Government Policies are of course of the leading core reasons for pricing/pay scale issues
  
  
  - Whether we like it or not, forcing ISPs to block sites/services puts a lot of overhead on them such as having to pay for the time spent implementing deep packet inspection (DPI) solutions to perform Server Name Indication (SNI) blocking or something along those lines
  - A good friend of mine highlighted how there have been inconsistent government approaches on the [Adjusted Gross Revenue](https://www.business-standard.com/article/companies/agr-dues-cannot-be-recomputed-supreme-court-reserves-order-121071901407_1.html) issue and that the government often requires a lot of effort in order to meet licensing and compliance requirements

*Below is an example of very low pricing. This is not a promotion nor an advertisement for the source.*

[![](assets/inline/image.png)](assets/inline/image.png)

_Figure 1 – An advertisement offering 250Mbps at just INR 167 + GST on tachyonbroadband.com_

In summary, the mental health of network operators in India is often under strain, (though there may be exceptions) and thus they cannot work efficiently which in turn results in bad network configuration and this is made worse by such low pricing, which in turns generates low revenue which in turns creates more problems.

There is one exception to the above — an ISP may be run by the proprietors themselves, who have full control over their networks (perhaps excluding last-mile).

However, in India, I know of many cases where the proprietor is not trained nor educated in computer science engineering or network engineering. In some cases, they simply copy/paste a configuration from the web, take random advice from AAA/RADIUS providers (who have too much of a focus on PPPoE and bad MTU, to begin with) and voila! We’ve got ourselves a network with five NAT layers and wonder why customers complain!

I have even heard of an operator in a remote location who never used any digital devices, does not know how to operate a laptop or smartphone, and is running a delegated network (leased out from an ISP). In these cases, the customer suffers.

## Issues with education

Now, this is a vast and complex topic, but I will try my best to summarise it.

I will approach this subject from a computer science perspective (as network engineering **is**a sub-branch of computer science).

I can only speak to the situation in India as it stands, and based on my own schooling and the comments I received from network operators.

Much of the formal education does not focus on how to solve (simple) engineering problems even if computer science, mathematics and science are part of the curriculum. The focus is on obtaining high marks/grades in exams and not on developing problem-solving skills nor creative thinking.

I have personally been a victim of this ‘high marks/grades’ emphasis during my school and college education. Much of what I do and know now in the field of computer science came from self-study, my own experiments and exposure to the industry. I cannot remember any important concepts that I picked up from the education system.

Also, much of the college syllabus for engineering is outdated. A good friend of mine [talked](https://anuragbhatia.com/2013/07/my-life/end-of-college-life-experiences-from-last-few-years-and-more/) about this almost a decade ago and there have been no changes since (I graduated in 2019 and did a status check from 2021 college students).

The professors themselves, most of the time, have never even configured a simple inter-VLAN routing setup nor have any hands-on experience in computer networking.  Some seem driven more by [misconceptions](https://anuragbhatia.com/2013/05/my-life/should-connected-interface-ping/). There are also tales of [unprofessional lecturers](https://web.archive.org/web/20240225052928/https://thelogicalindian.com/trending/iit-roorkee-professor-calls-student-mentally-weak-for-not-attending-class-due-to-fathers-demise-draws-social-media-wrath-25083) (when I was in college a professor told me IPv6 is not required in network engineering).

## Language fluency

Another challenge is lack of English fluency, which prevents operators from being able to comprehend documentation on the web—much of the global Internet operates using English, and this can be a challenge in places where English isn’t the first language.

India has many different languages. Hindi is arguably the most common language in India (which I do not speak fluently) and many of the engineers who reached out to me for help or guidance had difficulty because English is not their first language. Some had to completely drop the idea of working with me, which is unfortunate. But all hope is not lost, as those who understand my documentation and guides sometimes help to translate it for others.

This problem applies to pretty much anywhere in the world where English fluency is not high.

Some of them, unfortunately, do not get the opportunity to learn/grow for financial reasons.

## Cultural factors

One thing to keep in mind is that network engineers in India (and much of South Asia) avoid Linux, DevOps and automation, which impacts the quality of deployments. This applies to both small and big ISP players.

More importantly, in modern-day networking pretty much [everything](https://twitter.com/ghostinthenet/status/1417334765926109187) is Linux based.

Network engineers often struggle with things like:

- Implementing iptables filtering in the correct order (input>forward>output)
- Properly configuring the various parameters offered by Linux for NATting
- Understanding why connection tracking should be disabled on an edge router
- Have a proper ticketing system, network management system, mail server and so on

All this stems from the lack of understanding of Linux networking concepts, whereas network engineers in the US/Europe have very different preferences and habits.

There are also some operators who do not understand how the software development life cycle works and why we should always keep the software we use up to date. A majority of network engineers’ work computers that I have seen still run on end-of-life Windows 7 or something similar. Security is simply not taken seriously.

## The impacts on networks

Combining all the factors and reasons laid out, the following is typically the result:

- There is a lack of qualified personnel or engineers who have a clear understanding of core network fundamentals (CCNA 200-301 level)
  
  
  - For example, some may have engineering degrees yet still tell the customer that their choice of Optical Network Terminal (ONT) model on the customer site affects routing to external networks. This has happened to me once with a big telco.
- It is common to see poorly designed networks (bad topology) with bad configuration. There are often no network security measures in place (all the layers of the OSI model).
  
  
  - They may even run on OS/firmware versions released years or months ago with security holes/unpatched bugs.
- Equipment may be poorly chosen, often from a random vendor, possibly with a reputation for [controversy](https://securityboulevard.com/2020/03/huawei-backdoors-explanation-explained/), and who has time to pentest and investigate these potential security problems while also running an ISP?
- For last-mile delivery, again due to cost factors, ISPs would typically go for rebrands/reskinned variants of Optical Line Terminals (OLTs) or ONTs, which can often have bad firmware or MTU-related problems among other things
- The usual packet loss (pun intended) occurring in communication between an engineer and their HR/Management

## What can we do?

****From my research and investigation, I have a few suggestions for ISPs:****

- Look at how you can give your employees a reasonable salary with a work-life balance:
  
  
  - Mental Health Matters!
- We need better and sustainable pricing of mobile/broadband plans
- Invest in staff training and education in the technical side of things:
  
  
  - Working hours is [not](https://hbr.org/2015/08/the-research-is-clear-long-hours-backfire-for-people-and-for-companies)****equal to work output
  - Networking concepts are not sufficient; they must understand computer science fundamentals as a whole. At the end of the day, all these things run on programming and software.
- Do a background check of any franchisee/local cable operator/local operator before leasing out connectivity to people who have never even touched a computer in their lives
  
  
  - The end-user suffers, and security goes out the window, among other things
- Consider hiring a certified network engineer at least for the initial architectural design and deployment, instead of randomly taking advice from AAA/RADIUS providers or someone else who simply is not cut out for the job
- Have a ticketing system in place for internal use

**My suggestions for network engineers are as follows:**

- Ensure that you fully understand [network fundamental](https://academy.apnic.net/en/catalog/)****concepts
- Learn Linux networking
- Take advantage of automation tools such as Ansible
- Take advantage of open-source solutions such as VyOS and Docker

It’s fine if you specialize in just a specific vendor and you may not be familiar with the command-line interface (CLI) of a different vendor. At the end of the day, it’s all Linux.

If you want to take your career further, get involved with your [Network Operators Group](https://www.apnic.net/community/support/network-operator-groups/). Train up, develop relationships, be an active member of the community in [ISOC](https://www.internetsociety.org/), [SANOG](https://www.sanog.org/) and the regional mailing lists.

****To any newbie/fresh college kid/anyone looking for a job:****

If network engineering is not something you love, if it is not fun for you, then I would recommend looking elsewhere. There is no meaning or victory in burning out your mental health, personal relationships and wellbeing for a job that you hate.

I will end this with the following:

Computer systems do not configure themselves (at least not yet anyway); good configuration comes from good human operators (who, in turn, require a good education, technical skills, mental health and wellbeing).

And always remember that we’re all part of one global, technical community. Only by sharing our experiences can we build on what we’ve achieved and work through any problems that emerge.
