import * as lit from '~/lit'
import {NewObservable} from '~/observable'

export const tagsObservable = NewObservable<string[]>([])

@lit.customElement('api-schema-tags')
export class TagsHTMLE extends lit.HTMLElement {

    @lit.observe({observable: tagsObservable})
    items: string[] = []

    render() {
        return lit.html`
            <nav>
                <ul>
                    <li class="summary">tags</li>
                    ${this.items.map(x => lit.html`<li class="tag">${x}</li>`)}
                </ul>
            </nav>
        `
    }

    static styles = lit.css`
        :host {
            overflow-y: scroll;
        }

        nav {
            padding: 32px;

            ul {
                margin: 0;
                padding: 0;
                list-style: none;

                li {
                    padding-bottom: 16px
                }

                .summary {
                    text-transform: uppercase;
                }
            }
        }
    `
}
