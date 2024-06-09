import type {PrimaryJSONSchema} from './kinds'
import { RefResolver } from 'json-schema-ref-resolver'

export function resolveReferences(rootSchema: PrimaryJSONSchema) {
    rootSchema.$id = 'rootSchema'
    const instance = new RefResolver()
    instance.addSchema(rootSchema)
    return instance.getDerefSchema('rootSchema')
}
