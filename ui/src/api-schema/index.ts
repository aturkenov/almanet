import {NewObservable} from '~/observable'
import * as lit from '~/lit'
import * as JSONFetch from '~/json-fetch'
import * as JSONSchema from '~/json-schema'
import * as Tags from './tags'
import './endpoint'

interface APIEndpoint {
    channel: string
    topic: string
    title: string
    tags: string[]
    description: string
    payload_json_schema: JSONSchema.PrimaryJSONSchema
    return_json_schema: JSONSchema.PrimaryJSONSchema
}

export const endpointsObservable = NewObservable<APIEndpoint[]>([])

export async function* fetchEndpoints(
    limit: number = 10,
    offset: number = 0,
) {
    while (true) {
        let endpoints = await JSONFetch.post(`/api/v1/endpoint/get-many?limit=${limit}&offset=${offset}`)
        yield endpoints
        if (endpoints.length < limit) {
            break
        }
        offset += endpoints.length
    }
}

export async function loadSchema() {
    for await (const endpoints of fetchEndpoints()) {
        endpointsObservable.value = [...endpointsObservable.value, ...endpoints]
    }

    const tagSet = new Set<string>()
    for (const endpoint of endpointsObservable.value) {
        for (const tag of endpoint.tags) {
            tagSet.add(tag)
        }
    }
    Tags.tagsObservable.value = Array.from(tagSet)
}


@lit.customElement('api-schema')
export class IndexHTMLE extends lit.HTMLElement {

    @lit.state()
    tags: string[] = []

    @lit.state()
    endpoints: APIEndpoint[] = []

    async firstUpdated(changedProperties) {
        super.firstUpdated(changedProperties)
        Tags.tagsObservable.observe({
            next: v => {this.tags = v}
        })
        endpointsObservable.observe({
            next: v => {this.endpoints = v}
        })
        await loadSchema()
    }

    filterEndpointsByTag(
        v: string,
    ) {
        return this.endpoints.filter(x => x.tags.includes(v))
    }

    renderMain() {
        return this.tags.map(
            tag => lit.html`
                <h3>${tag}</h3>

                ${this.filterEndpointsByTag(tag).map(
                    endpoint => lit.html`
                        <api-endpoint
                            .channel=${endpoint.channel}
                            .topic=${endpoint.topic}
                            .title=${endpoint.title}
                            .description=${endpoint.description}
                            .payload_json_schema=${endpoint.payload_json_schema}
                            .return_json_schema=${endpoint.return_json_schema}
                        ></api-endpoint>
                    `
                )}
            `
        )
    }

    render() {
        return lit.html`
            <api-schema-tags></api-schema-tags>
            <main>
                ${this.renderMain()}
            </main>
        `
    }

    static styles = lit.css`
        :host {
            height: 100%;
            display: grid;
            grid-template-columns: 300px 1fr;
        }

        main {
            height: 100%;
            overflow-y: scroll;
        }
    `
}
