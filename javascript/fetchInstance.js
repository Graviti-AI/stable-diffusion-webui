const fetchPost = ({ data, url}) => {
    try {
        return fetch(url, {
            method: 'POST', 
            credentials: "include",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
    } catch(e) {
        return new Promise.reject(e);
    }
}

const fetchDelete = (url, data = {}) => {
    try {
        return fetch(url, {
            method: 'DELETE', 
            credentials: "include",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
    } catch(e) {
        return new Promise.reject(e);
    }
}

const fetchGet = (url, params) => {
    try {
        let queryParams = {
            method: 'GET',
            credentials: "include",
            cache: "no-cache"
        };
        if (params) {
            queryParams = {
                ...queryParams,
                ...params
            }
        }
        return fetch(url, queryParams)
    } catch(e) {
        return new Promise.reject(e);
    }
}

const fetchPut = (url, data = {}) => {
    try {
        return fetch(url, {
            method: 'PUT', 
            credentials: "include",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
    } catch(e) {
        return new Promise.reject(e);
    }
}
