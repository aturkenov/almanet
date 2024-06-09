export async function post(
    path: string,
    body: any = undefined
) {
    if (body !== undefined) {
        body = JSON.stringify(body)
    }
    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: body,
    }
    const response = await fetch(`http://localhost:8000${path}`, options)
    if (response.ok) {
        return await response.json()
    }
    throw new Error(response.statusText)
}
