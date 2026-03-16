# Broadband Forum GitHub Repositories Structure

## Key Repos for this MCP Server

### 1. BroadbandForum/cwmp-data-models (111MB, branch: master)
- CWMP data models in structured XML
- tr-181-2-*-cwmp-full.xml: Complete Device:2 data model for CWMP (~4MB each, 81 full files)
- tr-181-2-*-{component}.xml: Modular components (wifi, ip, ethernet, etc.) 10KB-260KB each
- tr-098-*-full.xml: Legacy InternetGatewayDevice data model
- cwmp-*.xsd: CWMP protocol XSD schemas
- XML format: <parameter name="" access="">, <object>, <component>, <description>, types, ranges, enumerations
- Latest version: tr-181-2-20-1 (as of 2026-03)

### 2. BroadbandForum/usp-data-models (57MB, branch: master)
- USP data models in structured XML (same format as CWMP)
- tr-181-2-*-usp-full.xml: Complete Device:2 for USP
- Has USP-specific components: wifi-usp.xml, softwaremodules-usp.xml, moca-usp.xml
- Also has tr-104, tr-135, tr-140 data models

### 3. BroadbandForum/usp (41MB, branch: master)
- Full USP TR-369 specification in Markdown
- specification/*/index.md: ~20 sections (architecture, messages, mtp/*, security, discovery, extensions/*)
- specification/usp-msg-1-{0..5}.proto: All USP Message protobuf versions
- specification/usp-record-1-{0..5}.proto: All USP Record protobuf versions
- api/swagger-usp-controller-v1.yaml: Controller API
- faq/: FAQs

### Other Potentially Useful Repos
- BroadbandForum/bbfreport: Official BBF data model report tool (reference for XML parsing)
- BroadbandForum/device-data-model: Upstream Device:2 source with specification/
- BroadbandForum/cwmp-xml-tools: DEPRECATED, old XML tools

## XML Data Model Format
```xml
<dm:document xmlns:dm="urn:broadband-forum-org:cwmp:datamodel-1-10">
  <import file="..." spec="...">
    <dataType name="..."/>
    <component name="..."/>
  </import>
  <component name="...">
    <parameter name="..." access="readWrite" mandatory="true" version="2.15">
      <description>...</description>
      <syntax>
        <unsignedInt><range maxInclusive="255"/><units value="dBm"/></unsignedInt>
      </syntax>
    </parameter>
  </component>
</dm:document>
```

## Key Insight: -full.xml Files
The `-full.xml` files have ALL imports resolved and contain the entire data model expanded.
These are the best files to parse for a complete index without dealing with cross-file imports.

## GitHub API Strategy (verified 2026-03-16)
- Trees API (`/git/trees/master?recursive=1`) returns all file paths in 1 request per repo
- Raw content (`raw.githubusercontent.com`) has no rate limit -- use for downloads
- GitHub Contents API has 60/hr limit (unauthenticated) -- avoid for bulk operations
- Latest versions as of 2026-03: tr-181-2-20-1 (both CWMP and USP full XMLs)
- USP specification: 20 markdown files under specification/, 12 proto files
- Total useful data ~12-15MB vs ~209MB for full clones