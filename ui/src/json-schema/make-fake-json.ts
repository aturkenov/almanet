import type {PrimaryJSONSchema} from './kinds'
import JSONSchemaFaker from 'json-schema-faker'

export function makeFakeJSON(rootSchema: PrimaryJSONSchema) {
    return JSONSchemaFaker.generate(rootSchema)
}
