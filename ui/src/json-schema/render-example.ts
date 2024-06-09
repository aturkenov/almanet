import { codeToHtml } from '../code-to-html'

import * as lit from '../lit'

import type {PrimaryJSONSchema} from './kinds'
import { makeFakeJSON } from './make-fake-json'

export function renderExample(rootSchema: PrimaryJSONSchema) {
    const jsonExample = makeFakeJSON(rootSchema)
    const jsonCode = JSON.stringify(jsonExample)
    const jsonHTML = codeToHtml(jsonCode, 'json')
    return lit.unsafeHTML(jsonHTML)
}
