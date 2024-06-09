import {LitElement, html, unsafeCSS} from 'lit'
import {customElement, property, state, query} from 'lit/decorators.js'

import * as monaco from 'monaco-editor'
import monaco_styles from 'monaco-editor/min/vs/editor/editor.main.css?inline'
import editor_worker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import json_worker from 'monaco-editor/esm/vs/language/json/json.worker?worker'

// @ts-ignore
self.MonacoEnvironment = {
	getWorker(_: any, label: string) {
		if (label === 'json') {
			return new json_worker()
		}
		return new editor_worker()
	}
}

@customElement('text-editor')
export class TextEditorHTMLE extends LitElement {

    @property()
    value: string = ''

    @property()
    options: monaco.editor.IStandaloneEditorConstructionOptions = {
        language: 'json',
        theme: 'vs-dark',
    }

    @query('#container')
    container: HTMLElement

    @state()
    editor: monaco.editor.IStandaloneCodeEditor

    firstUpdated(): void {
        this.editor = monaco.editor.create(this.container, this.options)
        this.editor.setValue(this.value)
    }

    static styles = unsafeCSS(monaco_styles)

    render() {
        return html`
            <div
                id="container"
                style="width: 100%; height: 400px"
            ></div>
        `
    }
}