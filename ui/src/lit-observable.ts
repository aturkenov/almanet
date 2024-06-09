import { property as litProperty } from 'lit/decorators/property.js'
import type {Observable} from '~/observable'

export type ObserveOptions = {
    observable: Observable
} 

export function observe({observable, ...options}: ObserveOptions) {
    const litStateDecorator = litProperty({
        ...options,
        state: true,
        attribute: false,
    })
    return function (target, propertyName) {
        target.constructor.addInitializer(
            instance => {
                observable.observe({
                    next(v) {
                        instance[propertyName] = v
                    },
                })
            }
        )
        return litStateDecorator(target, propertyName)
    }
}
