import { getHighlighterCore } from 'shiki/core'
import getWASM from 'shiki/wasm'

const highlighter = await getHighlighterCore({
    themes: [
      import('shiki/themes/material-theme-ocean.mjs')
    ],
    langs: [
      import('shiki/langs/json.mjs'),
    ],
    loadWasm: getWASM,
})

export function codeToHtml(code: string, language: string) {
    const options = {lang: language, theme: 'material-theme-ocean'}
    return highlighter.codeToHtml(code, options)
}
