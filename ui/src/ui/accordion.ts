import * as lit from '../lit'

@lit.customElement('ui-accordion')
export class Accordion extends lit.HTMLElement {

    @lit.property()
    open: boolean = false

    toggle(e: Event): void {
        this.open = !this.open
        this.dispatchEvent(new CustomEvent('change', {detail: this.open}))
    }

    render() {
        return lit.html`
            <style>
                .accordion-summary {
                    width: 100%;
                    display: block;
                    text-align: left;
                    border: none;
                    padding: 0;
                    cursor: pointer;
                    background: transparent;
                }

                .hide-accordion-body {
                    display: none;
                }
            </style>

            <div class="accordion">
                <button class="accordion-summary" @click=${this.toggle}>
                    <slot name="summary"></slot>
                </button>

                <div class="accordion-body ${lit.classMap({'hide-accordion-body': !this.open})}">
                    <slot></slot>
                </div>
            </div>
        `
    }
}
