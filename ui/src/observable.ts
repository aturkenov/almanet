export type Observer<T=any> = {
    next: (v: T) => void
    complete?: () => void
}

export function NewObservable<T=any>(defaultValue: T = undefined) {
    let lastValue: T = defaultValue
    let observers: Observer<T>[] = []
    return {
        observe(observer: Observer<T>): void {
            observers.push(observer)
        },

        get value(): T | undefined {
            return lastValue
        },

        set value(v: T) {
            lastValue = v
            for (const i of observers) {
                i.next(v)
            }
        },

        complete(): void {
            for (const i of observers) {
                if (i.complete === undefined) {
                    continue
                }
                i.complete()
            }
            observers = []
        },
    }
}

export type Observable = ReturnType<typeof NewObservable>
