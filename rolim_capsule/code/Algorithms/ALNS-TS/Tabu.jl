
function MakespanTS(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Evaluates the machine span of a machine using the TS representation

    CT = zeros(Int32, m)
    count::Int16 = 1 
    
    for i in eachindex(sol)
        if sol[i] < 0
            count += 1
        else
            if i != n+m-1
                if sol[i+1] >= 1
                    CT[count] += p[count, sol[i]]+S[count][sol[i],sol[i+1]]
                else
                    CT[count] += p[count, sol[i]]
                end
            else
                CT[count] += p[count, sol[i]]
            end
        end
    end
    
    Cmax::Int32 = maximum(CT)

    return(Cmax)
end

function SwapJobPar(sol::Vector{Int16}, m::Int8, n::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, Cmax::Int32)
    #----- Evaluates the swap between partitioning symbols and jobs

    PosPar = zeros(Int16, m-1)
    count::Int16 = 1
    S1::Int16 = 0 # S1 - First element of the swap (Always a partitioning symbol)
    S2::Int16 = 0 # S2 - Second element of the swap (Always a job)
    Best_Cmax::Int32 = Cmax
    eval::Int64 = 0
    
    for j in 1:n+m-1
        if sol[j] < 1
            PosPar[count] = j
            count += 1
        end
        if count > m-1
            break
        end
    end
    
    for i in PosPar
        for j in 1:n+m-1
            if i != j
                T1::Int16 = sol[j]
                T2::Int16 = sol[i]
                sol[j] = T2
                sol[i] = T1
                New_Cmax = MakespanTS(sol, m, n, p, S)
                eval += 1
                
                if New_Cmax < Best_Cmax
                    Best_Cmax = New_Cmax
                    S1 = i 
                    S2 = j
                end

                sol[j] = T1
                sol[i] = T2
            end
        end
    end
    
    return(S1, S2, Best_Cmax, eval)
end

function CopyMachine(sol::Vector{Int16}, m::Int8, n::Int16, M::Int8)
    #----- Returns a copy of the jobs assigned to a machine
    
    ME = Int16[]
    count::Int16 = 1 

    for i in 1:n+m-1
        if sol[i] < 0 
            count += 1
        end
        if count == M && sol[i] > 0
            push!(ME, sol[i])
        end
        if count > M
            break 
        end
    end
    
    return(ME)
end

function InsertMachine(sol::Vector{Int16}, M::Vector{Int16}, midx::Int8)
    #----- Inserts the jobs into a machine

    if midx == 1
        pos::Int16 = 1

        for k in M
            insert!(sol, pos, k)
            pos += 1
        end
    else
        pos = 0
        mc::Int8 = 1

        for l in eachindex(sol)
            if sol[l] < 0
                mc += 1
                if mc == midx
                    pos = l+1
                    break 
                end
            end
        end

        for k in M
            insert!(sol, pos, k)
            pos += 1
        end   
    end
end

function SwapMachine(sol::Vector{Int16}, M1::Vector{Int16}, M2::Vector{Int16},
    i::Int8, j::Int8)
    #----- Swaps two different machines
    
    filter!(x -> !(x in M1), sol)
    filter!(x -> !(x in M2), sol)
    
    InsertMachine(sol, M2, i)
    InsertMachine(sol, M1, j)
end

function SwapParPar(sol::Vector{Int16}, m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, Best_Cmax::Int32)
    #----- Evaluates the swap between partitioning symbols

    BM1::Int8 = 0 # Best machine swap (Always a machine with lower index in relation to BM2)
    BM2::Int8 = 0 # Best machine swap (Always a machine with higher index in relation to BM1)
    Iprv::Bool = false
    eval::Int64 = 0

    for i::Int8 in 1:m
        for j::Int8 in 1:m
            if i != j && i < j
                M1 = CopyMachine(sol, m, n, i) # Copy the elements of machine i
                M2 = CopyMachine(sol, m, n, j) # Copy the elements of machine j
                
                SwapMachine(sol, M1, M2, i, j) # Swaps machines i and j
                New_Cmax = MakespanTS(sol, m, n, p, S) # Evaluates the makespan
                eval += 1
               
                if New_Cmax < Best_Cmax
                    Best_Cmax = New_Cmax
                    BM1 = i
                    BM2 = j
                    Iprv = true
                end

                SwapMachine(sol, M1, M2, j, i)
            end
        end
    end

    return(BM1, BM2, Iprv, Best_Cmax, eval)
end

function ExecuteMove(sol::Vector{Int16}, m::Int8, n::Int16, S1::Int16, S2::Int16,
    BM1::Int8, BM2::Int8, Iprv::Bool, Iter::Int64, TabuList::Matrix{Int32},
    Cmax::Int32, Best_Cmax::Int32)
    #----- In case of improvement, executes the best ExecuteMove

    if Iprv == true # For swapping two different machines 
        if Cmax < Best_Cmax 
            TabuList[n+BM1, BM2] = Iter+n+m-1

            M1 = CopyMachine(sol, m, n, BM1)
            M2 = CopyMachine(sol, m, n, BM2)

            SwapMachine(sol, M1, M2, BM1, BM2)
            Best_Cmax = Cmax

        elseif TabuList[n+BM1, BM2] <= Iter
            TabuList[n+BM1, BM2] = Iter+n+m-1

            M1 = CopyMachine(sol, m, n, BM1)
            M2 = CopyMachine(sol, m, n, BM2)

            SwapMachine(sol, M1, M2, BM1, BM2)
        end
    else # For swapping a job and a partitioning symbol 
        if S1 != 0 && S2 != 0
            PAR::Int16 = sol[S1]
            JOB::Int16 = sol[S2]
            TABU1::Int16 = n + (PAR * -1) # The position 1 to mark the tabu move 
            TABU2::Int16 = JOB # The position 2 to mark the tabu move 
            
            if Cmax < Best_Cmax
                TabuList[TABU2, TABU1] = Iter+n+m-1

                T1::Int16 = sol[S1]
                T2::Int16 = sol[S2]
                sol[S2] = T1
                sol[S1] = T2

            elseif TabuList[TABU2, TABU1] <= Iter # Aspiration criterion
                TabuList[TABU2, TABU1] = Iter+n+m-1

                T1 = sol[S1]
                T2 = sol[S2]
                sol[S2] = T1
                sol[S1] = T2 
            end
        end
    end
end

function TabuSearch(sol::Vector{Int16}, m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    Iter::Int64, TabuList::Matrix{Int32}, Best_Cmax::Int32)
    #----- Executes the Improved Tabu Search

    eval::Int64 = 0

    Cmax::Int32 = MakespanTS(sol, m, n, p, S) # Calculates the makespan of the current solution
    eval += 1
    
    #----- Neighborhood evaluation

    S1, S2, Cmax, ev = SwapJobPar(sol, m, n, p, S, Cmax)
    eval += ev

    BM1, BM2, Iprv, Cmax, ev = SwapParPar(sol, m, n, p, S, Cmax)
    eval += ev

    # Executes a move in case of improvement

    ExecuteMove(sol, m, n, S1, S2, BM1, BM2,
    Iprv, Iter, TabuList, Cmax, Best_Cmax)
    
    return(Cmax, eval)
end