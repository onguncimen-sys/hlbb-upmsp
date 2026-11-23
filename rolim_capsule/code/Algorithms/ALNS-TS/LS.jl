function MakespanLS(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Evaluates the machine span using the LS representation

    CT = zeros(Int32, m)
    count::Int16 = 1 
    
    for i in eachindex(sol)
        if sol[i] < 0
            count += 1
        else
            if i != n+m-1
                if sol[i+1] > 0
                    CT[count] += p[count, sol[i]]+S[count][sol[i],sol[i+1]]
                else
                    CT[count] += p[count, sol[i]]
                end
            else
                CT[count] += p[count, sol[i]]
            end
        end
    end

    return(CT)
end

function MachineSpanLS(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, M::Int8)
    #----- Evaluates the machine span of a given machine

    CT::Int32 = 0
    mc::Int8 = 1

    for i in 1:n+m-1
        if sol[i] < 0 
            mc += 1
            if mc > M
                break 
            end
        else 
            if i != n+m-1 && mc == M
                if sol[i+1] > 0 
                    CT += p[mc, sol[i]]+S[mc][sol[i],sol[i+1]]
                else
                    CT += p[mc, sol[i]]
                end 
            elseif i == n+m-1 && mc == M
                CT += p[mc, sol[i]]
            end
        end
    end
    
    return(CT)
end

function MachineLen(sol::Vector{Int16}, m::Int8, n::Int16, M::Int8)
    #----- Counts the number of jobs in machine M
    
    len::Int16 = 0
    mc::Int8 = 1

    for i in 1:n+m-1
        if sol[i] < 0 
            mc += 1
            if mc > M
                break
            end
        end
        if sol[i] > 0 && mc == M 
            len += 1
        end 
    end
    
    return(len)
end

function MachineStart(sol::Vector{Int16}, n::Int16, m::Int8, M::Int8)
    #----- Determine the position that a machine starts in the current solution 

    mc::Int8 = 1 # Machine counter
    pc::Int16 = 1 # Position counter

    if M != 1
        for i in 1:n+m-1
            if sol[i] < 0 
                mc += 1
                if mc == M
                    pc = i+1
                    break
                end
            end
        end
    end
    
    return(pc)
end

function N1(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, OF::Vector{Int32})
    #----- Executes neighborhood N1 

    l::Vector{Int8} = sortperm(OF, rev = true)
    S1::Int16 = 0 # Save the position of the best swap
    S2::Int16 = 0 # Save the position of the best swap
    MS = MachineStart(sol, n, m, l[1]) # Starting position of the machine with highest makespan
    len = MachineLen(sol, m, n, l[1]) # Length of the machine with highest makespan
    B::Int32 = OF[l[1]]
    Iprv::Bool = false
    eval::Int64 = 0 
    
    if l[1] == 1
        END::Int16 = MS+len 
    else 
        END = MS+len-1
    end
    
    for j in MS:END
        for k in j+1:MS+len-1
            T1::Int16 = sol[j]
            T2::Int16 = sol[k]
            sol[j] = T2
            sol[k] = T1

            NCmax::Int32 = MachineSpanLS(sol, m, n, p, S, l[1])
            eval += 1

            if NCmax < B
                B = NCmax
                S1 = j 
                S2 = k
            end

            sol[j] = T1
            sol[k] = T2
        end
    end

    if S1 != 0 && S2 != 0
        T::Int16 = sol[S1]
        sol[S1] = sol[S2]
        sol[S2] = T
        OF[l[1]] = MachineSpanLS(sol, m, n, p, S, l[1])
        eval += 1
        Iprv = true
    end
    
    return(Iprv, eval)
end

function N2(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, OF::Vector{Int32})
    #----- Executes neighborhood N2

    IOF = deepcopy(OF)
    S1::Int16 = 0 # Save the position of the best swap
    S2::Int16 = 0 # Save the position of the best swap
    TAG::Int32 = 0 # Stores the best swap
    Iprv::Bool = false
    eval::Int64 = 0
    
    for i in 1:m
        MS1 = MachineStart(sol, n, m, i)
        len1 = MachineLen(sol, m, n, i)     
        END1::Int16 = MS1+len1-1
           
        for j in MS1:END1
            for k in 1:m
                if i != k && i < k
                    MS2 = MachineStart(sol, n, m, k)
                    len2 = MachineLen(sol, m, n, k)
                    END2::Int16 = MS2+len2-1
                    B::Int32 = OF[i] + OF[k]

                    for l in MS2:END2
                        T1::Int16 = sol[j]
                        T2::Int16 = sol[l]

                        sol[j] = T2 
                        sol[l] = T1 

                        IOF[i] = MachineSpanLS(sol, m, n, p, S, i)
                        eval += 1
                        IOF[k] = MachineSpanLS(sol, m, n, p, S, k)
                        eval += 1

                        NSum::Int32 = IOF[i] + IOF[k]
                        DELTA::Int32 = B - NSum

                        if DELTA > TAG && DELTA > 0
                            TAG = DELTA
                            S1 = j
                            S2 = l
                        end

                        sol[j] = T1
                        sol[l] = T2
                        IOF[i] = OF[i]
                        IOF[k] = OF[k]
                    end
                end
            end
        end
    end

    if S1 != 0 && S2 != 0
        T::Int16 = sol[S1]
        sol[S1] = sol[S2]
        sol[S2] = T
        OF = MakespanLS(sol, m, n, p, S)
        eval += 1
        Iprv = true
    end

    return(Iprv, eval)
end

function N3(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, OF::Vector{Int32})
    #----- Executes neighborhood N3

    B = deepcopy(OF)
    R::Int16 = 0 # Position of the removed element from the solution 
    I::Int16 = 0 # Position of insertion of the improved solution 
    Cmax::Int32 = maximum(OF) # Stores the best movement
    Iprv::Bool = false
    eval::Int64 = 0 

    for i in 1:n+m-1
        JOB::Int16 = sol[i]
        deleteat!(sol, i)

        for j in 1:n+m-1 
            if i != j 
                insert!(sol, j, JOB)
                IOF = MakespanLS(sol, m, n, p, S)
                eval += 1
                NCmax::Int32 = maximum(IOF)
                
                if NCmax < Cmax 
                    Cmax = NCmax

                    for k in 1:m 
                        B[k] = IOF[k]
                    end

                    R = i 
                    I = j
                end

                deleteat!(sol, j)
            end
        end

        insert!(sol, i, JOB)
    end

    if R != 0 && I != 0
        JOB = sol[R]
        deleteat!(sol, R)
        insert!(sol, I, JOB)

        for i in 1:m 
            OF[i] = B[i]
        end

        Iprv = true
    end
    
    return(Iprv, eval)
end

function VND(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, OF::Vector{Int32})
    #----- Executes the VND

    Nmax::Int8 = 3
    N = collect(Int8, 1:Nmax)
    No::Int8 = 1
    eval::Int64 = 0
    
    while No <= Nmax
        w::Int8 = rand(1:length(N))

        if N[w] == 1

            Iprv, ev = N1(sol, m, n, p, S, OF)
            eval += ev

        elseif N[w] == 2 

            Iprv, ev = N1(sol, m, n, p, S, OF)
            eval += ev

        elseif N[w] == 3

            Iprv, ev = N1(sol, m, n, p, S, OF)
            eval += ev

        end

        if Iprv == false
            No += 1
            deleteat!(N, w)
        end
    end

    return(eval)
end

function INEX_Swap(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, OF::Vector{Int32})
    #----- Performs internal and external swap

    IOF = deepcopy(OF) # Incumbent objective function 
    l::Vector{Int8} = sortperm(OF, rev = true)
    S1::Int16 = 0 # Save the position of the best swap
    S2::Int16 = 0 # Save the position of the best swap
    TAG::Int32 = 999999 # Stores the swap with the smallest difference
    eval::Int64 = 0
    
    for i in 2:m
        HP = MachineStart(sol, n, m, l[1]) # HP is the start of the machine with highest cost
        LP = MachineStart(sol, n, m, l[i]) # LP is the start of the machine with lower cost
        B::Int32 = OF[l[1]] + OF[l[i]] # Stores the sum of the costs of the two machines
        C1::Int16 = HP # Counter for the highest machine
        C2::Int16 = LP # Counter for the lowest machine
        LEN1::Int16 = MachineLen(sol, m, n, l[1])
        LEN2::Int16 = MachineLen(sol, m, n, l[i])

        if LEN1 == 0 || LEN2 == 0
            return(eval)
        end

        while sol[C1] > 0
            C2 = LP
            while sol[C2] > 0
                T1::Int16 = sol[C1]
                T2::Int16 = sol[C2]

                sol[C1] = T2
                sol[C2] = T1

                IOF[l[1]] = MachineSpanLS(sol, m, n, p, S, l[1])
                eval += 1
                IOF[l[i]] = MachineSpanLS(sol, m, n, p, S, l[i])
                eval += 1

                NSum::Int32 = IOF[l[1]] + IOF[l[i]]
                DELTA::Int32 = B - NSum
                
                if DELTA < TAG && DELTA > 0
                    TAG = DELTA
                    S1 = C1
                    S2 = C2
                end

                sol[C1] = T1 
                sol[C2] = T2
                IOF[l[1]] = OF[l[1]]
                IOF[l[i]] = OF[l[i]]

                C2 += 1

                if C2 > n+m-1 
                    break 
                end
            end

            C1 += 1

            if C1 > n+m-1 
                break 
            end
        end
    end

    if S1 != 0 && S2 != 0 
        T::Int16 = sol[S1]
        sol[S1] = sol[S2]
        sol[S2] = T
        OF = MakespanLS(sol, m, n, p, S)
        eval += 1
    end

    return(eval)
end

function INEX_Insertion(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, OF::Vector{Int32})
    #----- Performs internal and external insertion

    l::Vector{Int8} = sortperm(OF, rev = true)
    IOF = deepcopy(OF) # Incumbent objective function 
    R::Int16 = 0 # Saves the position of the job to be removed
    I::Int16 = 0 # Saves the insertion position
    eval::Int64 = 0 

    for i in 2:m
        HP = MachineStart(sol, n, m, l[1])
        LP = MachineStart(sol, n, m, l[i])
        B::Int32 = maximum(OF)

        for j in HP:n+m-1
            len = MachineLen(sol, m, n, l[i])

            if sol[j] > 0 
                JOB::Int16 = sol[j]
                deleteat!(sol, j)
            else
                break
            end

            if LP == 1
                BGN::Int16 = LP
                END::Int16 = LP + len 
            else
                BGN = LP - 1
                END = LP + len - 1
            end
            
            for k in BGN:END
                insert!(sol, k, JOB)
                IOF[l[1]] = MachineSpanLS(sol, m, n, p, S, l[1])
                eval += 1
                IOF[l[i]] = MachineSpanLS(sol, m, n, p, S, l[i])
                eval += 1

                NCmax::Int32 = maximum(IOF)
                
                if NCmax < B
                    B = NCmax
                    R = j 
                    I = k
                end

                deleteat!(sol, k)

                IOF[l[1]] = OF[l[1]]
                IOF[l[i]] = OF[l[i]]
            end

            insert!(sol, j, JOB)
        end
    end
    
    if R != 0 && I != 0 
        JOB = sol[R]
        deleteat!(sol, R)
        insert!(sol, I, JOB)
        OF = MakespanLS(sol, m, n, p, S)
        eval += 1
    end

    return(eval)
end

function HCS(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, OF::Vector{Int32})
    #----- Executes the Highest Cost Swap (HCS)

    eval::Int64 = 0 

    eval += INEX_Swap(sol, m, n, p, S, OF)
    eval += INEX_Insertion(sol, m, n, p, S, OF)

    return(eval)
end

function LocalSearch(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, Iter::Int64)
    #----- Executes the VND or HCS

    eval::Int64 = 0

    OF = MakespanLS(sol, m, n, p, S) # Incumbent makespan
    eval += 1
    
    if Iter % 1000 == 0

        eval += VND(sol, m, n, p, S, OF)

    else

        eval += HCS(sol, m, n, p, S, OF)

    end

    Cmax::Int32 = maximum(OF)

    return(Cmax, eval)
end