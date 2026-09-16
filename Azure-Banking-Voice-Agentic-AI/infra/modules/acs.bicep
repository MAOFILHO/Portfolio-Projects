// Azure Communication Services: the resource that owns the phone number, and the Event Grid wiring
// that routes an incoming call to the voice agent's webhook.
//
// WRITTEN AGAINST AN ALREADY-LIVE RESOURCE. Unlike call-records-store.bicep and app-insights.bicep,
// this module does not describe something Phase 7 will provision for the first time -- the ACS
// resource, its Event Grid system topic, and the incoming-call event subscription were all created
// by hand in Phase 0 (2026-08-20) and have been live ever since. This module exists so a clean
// subscription can reach the same state via `make deploy`, per Phase 7's own exit criterion, and so
// re-running deploy against the live resource group is a no-op rather than a guess.
//
// THE PHONE NUMBER IS NOT IN THIS FILE, ANYWHERE, AND CANNOT BE.
//
// Verified live 2026-09-16 (`az provider show --namespace Microsoft.Communication`): the
// `Microsoft.Communication` resource provider registers no `phoneNumbers` or `phoneNumberOrders`
// resource type at all. Phone numbers are managed exclusively through ACS's data-plane REST API
// (connection-string authenticated, the same surface `az communication phonenumber list` uses),
// never through ARM/Bicep. There is no Bicep syntax that could declare, own, or delete this
// project's number -- not a gap this module has to guard against, a thing ARM cannot do. D5's
// `scripts/check_no_phone_number_release.py` still scans for the shape defensively (fails closed on
// a pattern that currently cannot match, the same posture B3's static check takes toward names it
// has never seen), and independently blocks the one real mechanism that *can* touch a number: the
// data-plane CLI/SDK purchase/release/cancel calls, wherever they might appear.
//
// **Still unverified, named rather than assumed**: whether `dataLocation` (below) forces
// delete-and-recreate on a Bicep property change, for this resource type, under Incremental mode.
// Not researched -- moot as long as this module's `dataLocation` always matches the live value,
// which it does by being hardcoded rather than parameterized. A future change to this value must
// not be made without that research done first, precisely because "moot for now" is not "safe by
// construction" the way the phone-number question above is.
//
// BEFORE THIS IS EVER DEPLOYED AGAINST A *DIFFERENT* SUBSCRIPTION (i.e. actually exercising the
// clean-subscription path Phase 7 promises), TWO THINGS MUST HAPPEN, IN THIS ORDER:
//
//   1. A real Canadian geographic number is purchased for that subscription, manually, through the
//      same wizard-gated, human-in-the-loop process Phase 0 used -- never through this module or
//      the deploy CLI. R-09 (CLAUDE.md, PROJECT_STATE.md): the Canadian geographic-number inventory
//      has been observed to lose entire localities within ~20 minutes, so this step is deliberately
//      not automated.
//   2. Marco types `APPROVED: Phase 7` for any resulting change to the live resource. Given
//      2026-09-16 for this file's own authoring; a *second* approval is still owed before `az
//      deployment group create` is ever actually run against the live resource group, per this
//      phase's own D1/D3 (Incremental-only, manual-dispatch-only).
//
// A diff touching this file is never auto-accepted: it can affect a billable resource, even though
// running it here is expected to be a no-op against what already exists.

// No `location` param: every resource in this module is `global` -- verified live 2026-09-16
// (`az communication list`, `az eventgrid system-topic list`). Unlike call-records-store.bicep and
// app-insights.bicep, which are canadacentral-regional, there is nothing here for a location
// parameter to apply to.

@description('ACS resource name. Matches the live resource -- verified 2026-09-16.')
param name string = 'acs-azure-banking-voice'

@description('The voice agent Container App\'s incoming-call webhook, e.g. "https://<app-fqdn>/api/incoming-call". Taken as a parameter rather than cross-referenced: there is still no main.bicep tying modules together (call-records-store.bicep\'s own header notes the same gap), so each module compiles and is reviewed in isolation.')
param voiceAgentWebhookUrl string

resource acs 'Microsoft.Communication/CommunicationServices@2025-09-01' = {
  name: name
  location: 'global'
  properties: {
    // Hardcoded, not parameterized -- see the header note on why this value must never drift from
    // what is live without the replacement-on-change question being researched first.
    dataLocation: 'Canada'
  }
}

// Auto-created by ACS itself when the resource is provisioned through the portal or CLI; declared
// here explicitly so Bicep owns it too, rather than leaving it as a resource this project depends on
// but never describes.
resource incomingCallTopic 'Microsoft.EventGrid/systemTopics@2025-02-15' = {
  name: '${name}-${uniqueString(acs.id)}'
  location: 'global'
  properties: {
    source: acs.id
    topicType: 'Microsoft.Communication.CommunicationServices'
  }
}

// Routes exactly one event type to exactly one destination -- the webhook that turns an inbound
// call into the voice agent's IncomingCall handler. Filtered to the one event type this project
// acts on; ACS emits others (call ended, recording, etc.) that this project does not subscribe to.
resource incomingCallSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2025-02-15' = {
  parent: incomingCallTopic
  name: 'azbank-p0-incoming-call'
  properties: {
    destination: {
      endpointType: 'WebHook'
      // `az bicep build` flags this with use-secure-value-for-secure-inputs. A known false positive
      // for this property -- the linter treats any endpointUrl as secret-shaped, but the voice
      // agent's webhook route is a public HTTPS endpoint by design (ACS has to reach it from
      // outside this project), not a credential.
      properties: {
        endpointUrl: voiceAgentWebhookUrl
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Communication.IncomingCall'
      ]
    }
    eventDeliverySchema: 'EventGridSchema'
    retryPolicy: {
      // Matches the live subscription's values -- verified 2026-09-16 (`az eventgrid system-topic
      // event-subscription list`), not the Event Grid default.
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
}

@description('The ACS resource ID. Consumed by anything needing to grant a role scoped to this resource, or by CLI tooling that reads the live phone number off the data-plane API using this resource\'s name.')
output acsResourceId string = acs.id

@description('The ACS resource name, for data-plane lookups (az communication phonenumber list) that this module deliberately does not perform itself.')
output acsResourceName string = acs.name
