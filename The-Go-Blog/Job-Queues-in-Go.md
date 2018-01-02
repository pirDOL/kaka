## []()

### TLDR

### 翻译

Job Queues in Go
Constructs and snippets to build your job queue in Golang.
At RapidLoop, we use Go for nearly everything, including our server, service and uptime monitoring product OpsDash.

Go is quite good at asynchronous processing – goroutines and channels are arguably simpler, less error-prone and yet as powerful compared to async/awaits, promises and futures from other languages. Read on to see some interesting Go code around job queues.

The “No-Job-Queue” Job Queue
Let’s start with a bit of Zen – sometimes you just don’t need a job queue. Processing a job asynchronously can be done with:

go process(job)
This is indeed the best option for some needs, like firing off an email while handling an HTTP request. Whether you need a more elaborate infrastructure to deal with job processing depends mostly on scale and complexity. Queuing up your jobs and processing them in a controlled manner allows you to add more functionality like bounding the number of concurrent jobs, producer throttling and so on.

The Simplest Job Queue
Here is a simple queue and a worker that processes jobs off the queue. Goroutines and channels are just the right abstractions needed to code this into an elegant, tight piece.

func worker(jobChan <-chan Job) {
    for job := range jobChan {
        process(job)
    }
}

// make a channel with a capacity of 100.
jobChan := make(chan Job, 100)

// start the worker
go worker(jobChan)

// enqueue a job
jobChan <- job
The code basically creates a channel of Job objects, with a capacity of 100. It then starts a worker goroutine called worker. The worker pops jobs off the channel and processes them, one at a time. Jobs can be enqueued by pushing a Job object into the channel.

Although there are just a few lines of code, there’s a lot going on. First off, you have safe, correct, race-free code without having to mess with threads and mutexes.

Another feature is producer throttling.

Producer Throttling
The channel is created with a capacity of 100:

// make a channel with a capacity of 100.
jobChan := make(chan Job, 100)
which means that the enqueuing of a job like so:

// enqueue a job
jobChan <- job
will block, if there already are 100 jobs in the channel that the worker hasn’t got around to servicing. This is usually a good thing. You don’t want the backlog of jobs to grow too big if there is a SLA/QoS constraint, or even a reasonable assumption, that a job must finish within a certain amount of time. For example, if a job takes 1 second to finish in the worst case, with a channel capacity of 100 you’re looking at a worst case job finish time of 100 seconds.

If the channel is full, you’ll want your caller to back off for a while, typically. For example, it this were a REST API call, you might return a 503 (service unavailable) error code and document that the caller has to retry after a wait. This way, you’re applying backpressure up the caller chain to maintain a predictable quality of service.

Enqueueing Without Blocking
So how would you only try to enqueue, and fail if the operation would block? That way you can fail the job submission operation, and say return a 503. The trick is to use a select with a default clause:

// TryEnqueue tries to enqueue a job to the given job channel. Returns true if
// the operation was successful, and false if enqueuing would not have been
// possible without blocking. Job is not enqueued in the latter case.
func TryEnqueue(job Job, jobChan <-chan Job) bool {
    select {
    case jobChan <- job:
        return true
    default:
        return false
    }
}
With this, you can fail the submission this way:

if !TryEnqueue(job, chan) {
    http.Error(w, "max capacity reached", 503)
    return
}
Stopping the Worker
OK, so far so good. Now how can we stop the worker gracefully? Assuming that we’ve decided not to enqueue any more jobs and we want to let all the enqueued jobs finish, we can simply do:

close(jobChan)
Yes, that’s all there is. This works because the worker pops jobs off the queue with a for..range loop:

for job := range jobChan {...}
and this loop will exit when the channel is closed. All jobs enqueued into the channel before the channel was closed, will be popped out by the worker and processed as usual.

Waiting for the Worker
That was pretty easy. But close(jobChan) will not wait for the goroutine to exit. For that, we’ll use a sync.WaitGroup:

// use a WaitGroup 
var wg sync.WaitGroup

func worker(jobChan <-chan Job) {
    defer wg.Done()

    for job := range jobChan {
        process(job)
    }
}

// increment the WaitGroup before starting the worker
wg.Add(1)
go worker(jobChan)

// to stop the worker, first close the job channel
close(jobChan)

// then wait using the WaitGroup
wg.Wait()
With this, we’ll signal the worker to stop by closing the channel, and then wait for the worker goroutine to end with the wg.Wait().

Note that we’ve to increment the wait group before starting the goroutine, and decrement it once from within the goroutine when it exits, irrespective of the return path.

Waiting with a Timeout
The wg.Wait() will wait forever for the goroutine to exit. But what if we can’t afford to wait indefinitely?

Here’s a helper function that wraps wg.Wait and adds a timeout:

// WaitTimeout does a Wait on a sync.WaitGroup object but with a specified
// timeout. Returns true if the wait completed without timing out, false
// otherwise.
func WaitTimeout(wg *sync.WaitGroup, timeout time.Duration) bool {
    ch := make(chan struct{})
    go func() {
        wg.Wait()
        close(ch)
    }()
    select {
    case <-ch:
            return true
    case <-time.After(timeout):
            return false
    }
}

// now use the WaitTimeout instead of wg.Wait()
WaitTimeout(&wg, 5 * time.Second)
This now let’s you wait for your worker to exit, but places a bound on the amount of time it may take to do so.

Cancelling Workers
So far we have allowed our worker the liberty to finish processing it’s jobs even after we signalled it to stop. What if we need to say: “drop the rest, let’s get out of here!” to the worker?

Here’s how to do it with context.Context:

// create a context that can be cancelled
ctx, cancel := context.WithCancel(context.Background())

// start the goroutine passing it the context
go worker(ctx, jobChan)

func worker(ctx context.Context, jobChan <-chan Job) {
    for {
        select {
        case <-ctx.Done():
            return

        case job := <-jobChan:
            process(job)
        }
    }
}

// Invoke cancel when the worker needs to be stopped. This *does not* wait
// for the worker to exit.
cancel()
Basically, we create a “cancellable context”, and pass this to the worker. The worker waits on this, in addition to the job channel. The ctx.Done() becomes readable when cancel is invoked.

Like with the closing of the job channel, the cancel() will only signal, and does not wait. You’ll have to add the wait group code if you need to wait for the worker to exit – although the wait should be shorter as the worker will not process the remaining jobs.

However, there is a bit of a gotcha with this code. Consider the case when you have a backlog in the channel (so that <-jobChan will not block), and cancel() has been invoked (so that <-ctx.Done() also will not block). Since neither cases will block, the select has to choose between them. Fairly, one hopes.

Alas, in practice, this is not true. Not only is it plausible that “<-jobChan” is selected despite “<-ctx.Done()” also being non-blocking, it happens disconcertingly easily in practice. Even after a job is popped despite the cancellation and there are more pending, the situation remains the same – and the runtime is free to make the same “mistake” again.

To be fair (uh!), what we need is not fairness, but priority. The context cancellation case should have a higher priority than the other. However, there is no easy, built-in way to do this.

A flag might help:

var flag uint64

func worker(ctx context.Context, jobChan <-chan Job) {
    for {
        select {
        case <-ctx.Done():
            return

        case job := <-jobChan:
            process(job)
            if atomic.LoadUint64(&flag) == 1 {
                return
            }
        }
    }
}

// set the flag first, before cancelling
atomic.StoreUint64(&flag, 1)
cancel()
or equivalently use the context’s Err() method:

func worker(ctx context.Context, jobChan <-chan Job) {
    for {
        select {
        case <-ctx.Done():
            return

        case job := <-jobChan:
            process(job)
            if ctx.Err() != nil {
                return
            }
        }
    }
}

cancel()
[Updated: added Err()-based snippet also.]

We don’t check the flag/Err() before processing because since we popped the job, we might as well service it, to be consistent. Of course, if bailing out is a higher priority the check can be moved before the processing.

Bottom line? Either live with the fact that your worker might process a few extra jobs before exiting, or design your code carefully to work around the gotchas.

Cancelling Workers Without Context
context.Context is not magic. In fact, for this particular case, not having the context makes the code cleaner and clearer:

// create a cancel channel
cancelChan := make(chan struct{})

// start the goroutine passing it the cancel channel 
go worker(jobChan, cancelChan)

func worker(jobChan <-chan Job, cancelChan <-chan struct{}) {
    for {
        select {
        case <-cancelChan:
            return

        case job := <-jobChan:
            process(job)
        }
    }
}

// to cancel the worker, close the cancel channel
close(cancelChan)
This is essentially what (simple, non-hierarchical) context cancellation does behind the scenes too. The same gotchas exist, unfortunately.

A Pool of Workers
And finally, having multiple workers lets you increase your job concurrency. The easiest way is to simply spawn multiple workers and have them read off the same job channel:

for i:=0; i<workerCount; i++ {
    go worker(jobChan)
}
The rest of the code does not change. There will be multiple workers trying to read from the same channel – this is valid, and safe. Only one of the workers will successfully read, and the rest will block.

Again, there is a question of fairness. Ideally, if 100 jobs were processed by 4 workers, each would do 25. However, this may or may not be the case, and your code should not assume fairness.

To wait for workers to exit, add a wait group as usual:

for i:=0; i<workerCount; i++ {
    wg.Add(1)
    go worker(jobChan)
}

// wait for all workers to exit
wg.Wait()
[Updated: just one channel is needed for cancellation.]

For cancelling, you can create a single cancel channel, then close it to cancel all the workers.

// create cancel channel
cancelChan := make(chan struct{})

// pass the channel to the workers, let them wait on it
for i:=0; i<workerCount; i++ {
    go worker(jobChan, cancelChan)
}

// close the channel to signal the workers
close(cancelChan)
A Generic Job Queue Library?
On the face of it, job queues appear simple, and wonderfully suited to spinning off into a generic, reusable component. In reality though, the nitty-gritty details for each different place you’d want to use it will likely add to the complexity of the “generic” component. Couple this with the fact that it’s easier to write out a job queue in Go than in most other languages, you’re probably better off writing job queues tailored to each requirement.