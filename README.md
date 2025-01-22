# whatsoverhead
what aircraft is overhead?

live demo: [https://whatsoverhead.rickt.dev](https://whatsoverhead.rickt.dev)

## what is it

a self-contained python app that reports if any aircraft are overhead of a given location / set of coordinates. 

uses the free [adsb.fi](https://adsb.fi) [ADS-B API](https://github.com/adsbfi/opendata/blob/main/README.md). 

* static assets (frontend HTML/JS, a PNG and an .ico) are in [static](https://github.com/rickt/whatsoverhead/tree/main/static)
* scripts to build/push/deploy to GCP Cloud Run are in [scripts](https://github.com/rickt/whatsoverhead/tree/main/static)
* i deploy automatically on commits to GCP Cloud Run using a [workflow ](https://github.com/rickt/whatsoverhead/tree/main/.github/workflors)but you can put it wherever. 

## API endpoints
* health check
  * GET `/health`
  * description:
    * returns health status of the API
  * parameters:
    * none
  * response:
    ```
    {
       "status": "healthy"
    }
    ```

* nearest plane
  * GET `/nearest_plane`
  * description:
    * returns the nearest aircraft to the given coordinates within a specified distance
     * parameters:
       ```| Name   | Type   | Default | Description                           |
          |--------|--------|---------|---------------------------------------|
          | lat    | float  | None    | Latitude of the location (required).  |
          | lon    | float  | None    | Longitude of the location (required). |
          | dist   | float  | 5.0     | Search radius in kilometers.          |
          | format | string | json    | Response format (json or text).       |
       ```

## inspiration
inspiration for this came from John Wiseman's [whatsoverhead.com](https://whatsoverhead.com), which i loved! i wanted to know how it works and ended up writing my own version. 

