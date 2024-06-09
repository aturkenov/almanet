import {chevronUp, chevronDown} from '../icons'
import * as lit from '../lit'
import * as JSONSchema from '../json-schema'
import '~/ui/accordion'
import '~/text-editor'

@lit.customElement('api-endpoint')
export class EndpointHTMLE extends lit.HTMLElement {

    @lit.property()
    channel!: string

    @lit.property()
    topic!: string

    @lit.property()
    title!: string

    @lit.property()
    description!: string

    @lit.property()
    payload_json_schema!: JSONSchema.PrimaryJSONSchema

    @lit.property()
    return_json_schema!: JSONSchema.PrimaryJSONSchema

    @lit.state()
    accordionOpen: boolean = false

    async fetchEndpoint({detail: state}: CustomEvent) {
        this.accordionOpen = state
    }

    render() {
        return lit.html`
            <div class="endpoint">
                <ui-accordion @change=${this.fetchEndpoint}>
                    <div slot="summary" class="summary">
                        <div class="left">
                            <span class="channel">${this.channel}</span>
                            <span class="topic">${this.topic}</span>
                            <span class="title">${this.title}</span>
                        </div>
                        <div class="right">
                            <span>${this.accordionOpen ? chevronUp() : chevronDown()}</span>
                        </div>
                    </div>

                    <div class="body">
                        <div class="description">${this.description}</div>

                        <div class="payload-schema">
                            <div>payload example</div>
                            ${JSONSchema.renderExample(this.payload_json_schema)}
                        </div>

                        ${lit.when(this.return_json_schema,
                            () => lit.html`
                                <div class="return-schema">
                                    <div>return example</div>
                                    ${JSONSchema.renderExample(this.return_json_schema)}
                                </div>
                            `)
                        }
                    </div>
                </ui-accordion>
            </div>
        `
    }

    static styles = lit.css`
        .endpoint {
            border-radius: 5px;
            border: 1px solid #ccc;

            .summary {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 5px;

                .method {
                    font-size: 1.2em;
                    font-weight: bold;
                    text-transform: uppercase;
                }

                .topic {
                    font-size: 1.5em;
                    font-weight: bold;
                }
            }

            .body {
                padding: 10px;

                > * {
                    padding-top: 10px;
                    padding-bottom: 10px;
                }
            }
        }
    `
}
