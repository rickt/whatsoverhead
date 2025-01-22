# whatsoverhead
what aircraft is overhead?

live demo: [https://whatsoverhead.rickt.dev](https://whatsoverhead.rickt.dev)

## what is it

a self-contained python app that reports if any aircraft are overhead of a given location / set of coordinates. 

uses the free [adsb.fi](https://adsb.fi) [ADS-B API](https://github.com/adsbfi/opendata/blob/main/README.md). 

* static assets (frontend HTML/JS, a PNG and an .ico) are in [static](https://github.com/rickt/whatsoverhead/tree/main/static)
* scripts to build/push/deploy to GCP Cloud Run are in [scripts](https://github.com/rickt/whatsoverhead/tree/main/static)
* i deploy automatically on commits to GCP Cloud Run using a [workflow ](https://github.com/rickt/whatsoverhead/tree/main/.github/workflors)but you can put it wherever. 

## inspiration
inspiration for this came from John Wiseman's [whatsoverhead.com](https://whatsoverhead.com), which i loved! i wanted to know how it works and ended up writing my own version. 

