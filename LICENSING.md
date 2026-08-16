# Licensing

## Code, Scripts, and Tooling

Repository scripts and tooling are licensed under the MIT License.

- SPDX identifier: `MIT`
- Licence text: `LICENSES/MIT.txt`
- Applies to: `scripts/`, `Makefile`, and repository maintenance/tooling code
  unless a file states otherwise.
- Does not apply to: mirrored article text, mirrored images/media, spreadsheet
  data/content, third-party media, or external artefacts.

## Mirrored Blog Content

The public daryllswer.com site states that the site content is licensed under
Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
(`CC-BY-NC-SA-4.0`).

This repository mirrors that public content licence only for original
daryllswer.com article text/content covered by the site's default licence.
It does not infer a licence for reposted or otherwise separately owned
content.

- SPDX identifier: `CC-BY-NC-SA-4.0`
- Licence text: `LICENSES/CC-BY-NC-SA-4.0.txt`
- Applies to: mirrored original daryllswer.com text/content that has no
  explicit per-post rights exception.
- Does not apply to: repository scripts/tooling, third-party media, or external
  artefacts, or proprietary reposted content.

## Proprietary Swer Networks Reposts

`content/rights-registry.json` is the source record for explicit per-post
rights exceptions. A registry-marked post has matching structured `rights`
metadata in its post bundle and retains the source article's visible rights
notice; the registry does not alter GitHub Pages SEO metadata.

The BGP Router ID republication (WordPress ID `5324`) is proprietary Swer
Networks article text, all rights reserved. It is excluded from the
daryllswer.com `CC-BY-NC-SA-4.0` default. Media remains subject to its own
attribution or rights notice.

- Controlling archive notice:
  `LICENSES/SWER-NETWORKS-PROPRIETARY-CONTENT-NOTICE.txt`.
- Original publication URL: `https://www.swernetworks.com/blog/bgp-router-id-structuring-in-ipv6-native-networks/`.

## Third-Party Media and External Artefacts

Some posts may reference third-party media, external documents, embedded
services, spreadsheets, or externally hosted artefacts.

Do not assume third-party media or external artefacts are covered by either MIT
or `CC-BY-NC-SA-4.0`. Preserve provenance where practical and flag unclear
cases before redistribution.

## Proprietary Daryll Swer Brand Assets

`assets/readme/13_DS_Logo_Dark_Mode_SEO.png` and
`assets/brand/01_DS_Favicon_Dark_Mode.png` and its controlled derivative under
`assets/brand/derivatives/` are owner-provided proprietary Daryll Swer brand
assets. The former is used only as the repository README header; the favicon
master remains byte-for-byte preserved and the controlled derivative is copied
byte-for-byte to the GitHub Pages header and browser favicon.

- Copyright notice: `© 2026 Daryll Swer. All rights reserved.`
- Licence status: proprietary; no public copyright or trade mark licence is
  granted.
- Controlling legal notice:
  `LICENSES/DARYLL-SWER-PROPRIETARY-ASSET-NOTICE.txt`.
- Provenance and byte-preservation records:
  `assets/readme/ASSET_PROVENANCE.md`, `assets/readme/manifest.json`, and
  `assets/brand/ASSET_PROVENANCE.md`/`assets/brand/manifest.json`. These
  records are not licences.
- Excluded from: the MIT licence, `CC-BY-NC-SA-4.0`, and every other repository
  licence or content grant.

The notice reserves copying, distribution, modification, derivative use, and
brand use except where applicable law requires otherwise. The generated 512 px
Pages favicon is a proprietary derivative of the supplied source image. A
public GitHub repository still carries the limited service permissions in
GitHub's Terms of Service for hosting, viewing, and forking; this asset notice
grants no broader permission.

## Self-Hosted Fonts

The archive self-hosts `Poppins` and `Raleway` WOFF2 font files under
`assets/fonts/` and generated `docs/assets/fonts/`.

- Licence: SIL Open Font License 1.1, per the family-specific files
  `assets/fonts/OFL-Poppins.txt` and `assets/fonts/OFL-Raleway.txt`.
- Provenance/checksums: `assets/fonts/manifest.json`.
- Applies to: the font files only.
- Does not apply to: repository scripts/tooling, mirrored article content,
  mirrored media, spreadsheet content, or other third-party artefacts.
